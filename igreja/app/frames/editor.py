import os
import sys
import queue
import shutil
import tempfile
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.utils import HAS_DND, DND_FILES, create_no_window_flags, seconds_to_hms, _ext


VIDEO_EXTS = {"mp4", "avi", "mkv", "mov", "webm", "flv", "m4v"}


def is_video_file(path: str) -> bool:
    return _ext(path) in VIDEO_EXTS


def parse_time_to_seconds(value: str):
    text = (value or "").strip().replace(",", ".")
    if not text:
        return None

    parts = text.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError:
        return None
    return None


class EditorFrame(ttk.Frame):
    def __init__(self, master, on_status):
        super().__init__(master)
        self.on_status = on_status

        self.input_files = []
        self.file_durations = {}
        self.last_output = ""

        # Dynamically generated UI rows for each selected video (Trecho 1, 2, 3...)
        self.video_rows = []
        self.output_name_var = tk.StringVar()

        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="")
        self.is_running = False
        self.cancel_requested = False
        self.proc = None
        self.ui_queue = queue.Queue()

        self._build_ui()
        self.after(100, self._drain_ui_queue)

        if HAS_DND:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop_files)
            except Exception:
                pass

    def _build_ui(self):
        # Use a scrollable canvas so the UI fits in smaller windows and the user can reach
        # the bottom controls when the content grows.
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        # Scrollbar is shown only when needed (e.g. after a file is selected).

        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scroll_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", self._on_scrollable_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Start with scrollbar hidden; it appears only when needed.
        self._update_scrollbar_visibility()

        # Enable mouse wheel scrolling when pointer is over the content area.
        self.canvas.bind(
            "<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        )
        self.canvas.bind(
            "<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>")
        )

        card = ttk.Frame(self.scrollable_frame, padding=18)
        card.pack(fill="both", expand=True)

        header = ttk.Frame(card)
        header.pack(fill="x")
        ttk.Label(header, text="Editor de Video", style="SectionTitle.TLabel").pack(side="left")
        ttk.Separator(card).pack(fill="x", pady=12)

        files_frame = ttk.LabelFrame(card, text="Arquivos")
        files_frame.pack(fill="x")
        files_inner = ttk.Frame(files_frame, padding=12)
        files_inner.pack(fill="x")
        files_inner.columnconfigure(1, weight=1)

        ttk.Button(files_inner, text="Selecionar videos", command=self.select_files, bootstyle=WARNING).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(files_inner, text="Limpar", command=self.clear_files, bootstyle=DANGER).grid(
            row=0, column=1, sticky="w", padx=(10, 0)
        )
        ttk.Label(
            files_inner,
            text="Monte um video novo usando um trecho de cada arquivo. Use vazio para considerar o video inteiro.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 6))

        self.selection_label = ttk.Label(files_inner, text="Nenhum video selecionado", font=("Helvetica", 12))
        self.selection_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 6))

        if HAS_DND:
            ttk.Label(
                files_inner,
                text="Arraste e solte videos aqui para selecionar.",
                style="Muted.TLabel",
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 6))

        # Container for the list of selected videos (Trecho 1, Trecho 2, ...).
        self.videos_container = ttk.Frame(card)
        self.videos_container.pack(fill="x", pady=(2, 6))

        # Build initial empty list (no videos selected yet).
        self._rebuild_video_rows()

        options = ttk.LabelFrame(card, text="Opções", font=("Segoe UI", 14, "bold"))
        options.pack(fill="x", pady=(2, 6))
        options_inner = ttk.Frame(options, padding=12)
        options_inner.pack(fill="x")
        options.pack_forget()
        self.options_frame = options
        options_inner.columnconfigure(0, weight=1)
        options_inner.columnconfigure(1, weight=1)

        ttk.Label(options_inner, text="Ordem de montagem", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(options_inner, text="Nome do arquivo", font=("Segoe UI", 12, "bold")).grid(row=0, column=1, sticky="w")

        ttk.Label(options_inner, text="Seguir a ordem dos vídeos selecionados", font=("Segoe UI", 11)).grid(
            row=1, column=0, sticky="w", padx=(0, 20)
        )
        ttk.Entry(options_inner, textvariable=self.output_name_var, width=28).grid(row=1, column=1, sticky="ew")

        self.controls_frame = ttk.Frame(card)
        self.controls_frame.pack(fill="x", pady=(2, 6))
        self.run_btn = ttk.Button(self.controls_frame, text="Gerar video", command=self.start_processing, bootstyle=SUCCESS, state=DISABLED)
        self.run_btn.pack(side="left")
        self.cancel_btn = ttk.Button(self.controls_frame, text="Cancelar", command=self.cancel_processing, bootstyle=SECONDARY, state=DISABLED)
        self.cancel_btn.pack(side="left", padx=(10, 0))
        self.open_btn = ttk.Button(self.controls_frame, text="Abrir pasta do video", command=self.open_folder, bootstyle=INFO, state=DISABLED)
        self.open_btn.pack(side="left", padx=(10, 0))
        self.controls_frame.pack_forget()

        hint = ttk.Label(
            card,
            text="Formatos de tempo aceitos: 90, 01:30, 00:01:30.500",
            style="Muted.TLabel",
        )
        hint.pack(anchor="w", pady=(0, 6))

        self.progress_frame = ttk.Frame(card, padding=(10, 6))
        self.progress = ttk.Progressbar(self.progress_frame, orient=tk.HORIZONTAL, mode="determinate", variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x")
        ttk.Label(self.progress_frame, textvariable=self.status_var, font=("Helvetica", 11)).pack(anchor="w", pady=(6, 0))

        # Hide progress UI until processing starts.
        self._hide_progress()

        self._update_action_state()
        self._update_visibility()

    def select_files(self):
        filetypes = [
            ("Videos", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.m4v"),
            ("Todos", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="Selecione videos", filetypes=filetypes)
        if paths:
            self._set_files(list(paths))

    def _on_drop_files(self, event):
        items = self.tk.splitlist(event.data)
        paths = []
        for item in items:
            if os.path.isfile(item) and is_video_file(item):
                paths.append(os.path.abspath(item))
        if paths:
            self._set_files(paths)

    def _set_files(self, paths):
        uniq = []
        seen = set()
        for path in paths:
            abs_path = os.path.abspath(path)
            if not os.path.isfile(abs_path) or not is_video_file(abs_path):
                continue
            low = abs_path.lower()
            if low in seen:
                continue
            seen.add(low)
            uniq.append(abs_path)

        # Add new videos to the list (do not overwrite the existing ones).
        existing_set = {p.lower() for p in self.input_files}
        additions = []
        for path in uniq:
            if path.lower() not in existing_set:
                existing_set.add(path.lower())
                additions.append(path)

        if not additions:
            return

        self.input_files.extend(additions)
        self.file_durations.update({path: self._probe_duration(path) for path in additions})
        self.progress_var.set(0)
        self.status_var.set("")
        self.last_output = ""
        self.open_btn.config(state=DISABLED)

        self._refresh_file_info()
        self._refresh_output_name()
        self._update_action_state()
        self._update_visibility()
        self._update_scrollbar_visibility()

    def _refresh_file_info(self):
        if not self.input_files:
            self.selection_label.config(text="Nenhum video selecionado")
            self._rebuild_video_rows()
            self._update_visibility()
            return

        count = len(self.input_files)
        if count == 1:
            self.selection_label.config(text=f"1 video selecionado: {os.path.basename(self.input_files[0])}")
        else:
            self.selection_label.config(
                text=f"{count} videos selecionados: {os.path.basename(self.input_files[0])} + {os.path.basename(self.input_files[1])}"
            )

        self._rebuild_video_rows()
        self._update_visibility()
        # Ensure the action buttons are visible after selecting a video in smaller windows.
        self._scroll_to_bottom()
        self._update_scrollbar_visibility()

    def _rebuild_video_rows(self):
        """Rebuild the per-video segment editors (Trecho 1, Trecho 2, ...)."""
        # Clear existing rows
        for row in self.video_rows:
            try:
                row["frame"].destroy()
            except Exception:
                pass
        self.video_rows = []

        for idx, path in enumerate(self.input_files, start=1):
            row_frame = ttk.LabelFrame(self.videos_container, text=f"Trecho {idx}", font=("Segoe UI", 14, "bold"))
            row_frame.pack(fill="x", pady=(0, 6))

            base_name = os.path.basename(path)
            ttk.Label(row_frame, text=base_name).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(6, 2))
            ttk.Label(row_frame, text=self._duration_text(path), style="Muted.TLabel").grid(
                row=1, column=0, columnspan=4, sticky="w", padx=10, pady=(0, 6)
            )

            ttk.Label(row_frame, text="Início").grid(row=2, column=0, sticky="w", padx=(10, 6))
            ttk.Label(row_frame, text="Fim").grid(row=2, column=2, sticky="w", padx=(12, 6))

            start_var = tk.StringVar()
            end_var = tk.StringVar()
            ttk.Entry(row_frame, textvariable=start_var, width=18).grid(row=3, column=0, sticky="w", pady=(2, 8))
            ttk.Entry(row_frame, textvariable=end_var, width=18).grid(row=3, column=2, sticky="w", pady=(2, 8))

            remove_btn = ttk.Button(
                row_frame,
                text="Remover",
                bootstyle="danger",
                command=lambda p=path: self._remove_file(p),
            )
            remove_btn.grid(row=3, column=3, sticky="e", padx=(10, 0))

            self.video_rows.append({
                "path": path,
                "frame": row_frame,
                "start_var": start_var,
                "end_var": end_var,
            })

        self._update_scrollbar_visibility()

    def _refresh_output_name(self):
        if not self.input_files:
            self.output_name_var.set("")
            return
        if len(self.input_files) == 1:
            base = os.path.splitext(os.path.basename(self.input_files[0]))[0]
            self.output_name_var.set(f"{base}_editado.mp4")
            return
        self.output_name_var.set("video_montado.mp4")

    def _update_visibility(self):
        """Show/hide the editor sections depending on whether any file is selected."""
        if self.input_files:
            if not self.videos_container.winfo_ismapped():
                self.videos_container.pack(fill="x", pady=(2, 6))
            if not self.options_frame.winfo_ismapped():
                self.options_frame.pack(fill="x", pady=(2, 6))
            if not self.controls_frame.winfo_ismapped():
                self.controls_frame.pack(fill="x", pady=(2, 6))
        else:
            self.videos_container.pack_forget()
            self.options_frame.pack_forget()
            self.controls_frame.pack_forget()

        # Only show progress while processing is running.
        if self.is_running:
            self._show_progress()
        else:
            self._hide_progress()

    def _show_progress(self):
        if getattr(self, "progress_frame", None) and not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill="x", pady=(4, 2))

    def _hide_progress(self):
        if getattr(self, "progress_frame", None) and self.progress_frame.winfo_ismapped():
            self.progress_frame.pack_forget()

    def _scroll_to_bottom(self):
        """Scroll the editor view to the bottom so action buttons become visible."""
        if not getattr(self, "canvas", None):
            return
        if not getattr(self, "scrollbar", None) or not self.scrollbar.winfo_ismapped():
            return
        self.canvas.yview_moveto(1.0)

    def _on_scrollable_configure(self, event):
        # Adjust the scroll region to encompass the full content.
        if getattr(self, "canvas", None):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        # Keep the inner frame the same width as the canvas.
        try:
            self.canvas.itemconfig(self.scroll_window, width=event.width)
        except Exception:
            pass
        self._update_scrollbar_visibility()

    def _on_mousewheel(self, event):
        # Cross-platform mouse wheel scrolling support.
        if not getattr(self, "canvas", None):
            return
        # Windows / macOS
        delta = int(-1 * (event.delta / 120)) if hasattr(event, "delta") else 0
        self.canvas.yview_scroll(delta, "units")

    def _update_scrollbar_visibility(self):
        # Ensure geometry is updated before measuring.
        try:
            self.update_idletasks()
        except Exception:
            pass

        if not getattr(self, "canvas", None):
            return

        bbox = self.canvas.bbox("all")
        if not bbox:
            self.scrollbar.pack_forget()
            self.canvas.configure(yscrollcommand=None)
            return

        content_height = bbox[3] - bbox[1]
        visible_height = self.canvas.winfo_height()

        # If canvas isn't fully laid out yet, do nothing.
        if visible_height <= 1:
            return

        needs_scroll = content_height > visible_height + 10 and bool(self.input_files)
        if needs_scroll:
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(side="right", fill="y")
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
        else:
            self.scrollbar.pack_forget()
            self.canvas.configure(yscrollcommand=None)

    def _update_action_state(self):
        if self.is_running:
            self.run_btn.config(state=DISABLED)
            self.cancel_btn.config(state=NORMAL)
            return

        self.run_btn.config(state=NORMAL if self.input_files else DISABLED)
        self.cancel_btn.config(state=DISABLED)

    def clear_files(self):
        self.input_files = []
        self.file_durations = {}
        self.video_rows = []
        self.output_name_var.set("")
        self.progress_var.set(0)
        self.status_var.set("")
        self._hide_progress()
        self.last_output = ""
        self.open_btn.config(state=DISABLED)
        self._refresh_file_info()
        self._update_action_state()

    def _remove_file(self, path):
        self.input_files = [p for p in self.input_files if p.lower() != path.lower()]
        self.file_durations.pop(path, None)
        self._refresh_file_info()
        self._update_action_state()
        self._update_scrollbar_visibility()

    def start_processing(self):
        if self.is_running:
            return
        if not self.input_files:
            messagebox.showerror("Erro", "Selecione pelo menos um video.")
            return

        segments = self._build_segments()
        if not segments:
            return

        output_name = (self.output_name_var.get() or "").strip()
        if not output_name:
            messagebox.showerror("Erro", "Informe um nome para o arquivo de saida.")
            return
        if not output_name.lower().endswith(".mp4"):
            output_name += ".mp4"

        output_path = os.path.join(os.path.dirname(self.input_files[0]), output_name)
        normalized_output = os.path.abspath(output_path).lower()
        if normalized_output in {os.path.abspath(path).lower() for path in self.input_files}:
            messagebox.showerror("Erro", "Escolha um nome diferente do video original para evitar sobrescrita.")
            return

        self.is_running = True
        self.cancel_requested = False
        self.progress_var.set(0)
        self.status_var.set("Preparando...")
        self.on_status("Edicao iniciada...")
        self.run_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.open_btn.config(state=DISABLED)
        self._show_progress()
        self._update_action_state()

        threading.Thread(target=self._worker, args=(segments, output_path), daemon=True).start()

    def cancel_processing(self):
        if not self.is_running:
            return
        self.cancel_requested = True
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass

    def _build_segments(self):
        if not self.video_rows:
            messagebox.showerror("Erro", "Selecione pelo menos um video.")
            return None

        result = []
        for idx, row in enumerate(self.video_rows, start=1):
            segment = self._build_single_segment(
                path=row["path"],
                start_value=row["start_var"].get(),
                end_value=row["end_var"].get(),
                label=f"Trecho {idx}",
            )
            if segment is None:
                return None
            result.append(segment)

        if not result:
            messagebox.showerror("Erro", "Nao foi possivel montar os trechos selecionados.")
            return None

        return result

    def _build_single_segment(self, path, start_value, end_value, label):
        start = parse_time_to_seconds(start_value)
        end = parse_time_to_seconds(end_value)

        if start_value.strip() and start is None:
            messagebox.showerror("Tempo invalido", f"{label}: inicio invalido.")
            return None
        if end_value.strip() and end is None:
            messagebox.showerror("Tempo invalido", f"{label}: fim invalido.")
            return None
        if start is not None and start < 0:
            messagebox.showerror("Tempo invalido", f"{label}: o inicio nao pode ser negativo.")
            return None
        if end is not None and end < 0:
            messagebox.showerror("Tempo invalido", f"{label}: o fim nao pode ser negativo.")
            return None
        if start is not None and end is not None and end <= start:
            messagebox.showerror("Tempo invalido", f"{label}: o fim precisa ser maior que o inicio.")
            return None

        duration = self.file_durations.get(path)
        if duration is not None:
            if start is not None and start > duration:
                messagebox.showerror("Tempo invalido", f"{label}: o inicio ultrapassa a duracao do video.")
                return None
            if end is not None and end > duration:
                messagebox.showerror("Tempo invalido", f"{label}: o fim ultrapassa a duracao do video.")
                return None

        clip_duration = None
        if start is not None and end is not None:
            clip_duration = end - start
        elif end is not None:
            clip_duration = end
        elif start is not None and duration is not None:
            clip_duration = max(duration - start, 0.0)
        elif duration is not None:
            clip_duration = duration

        return {
            "path": path,
            "start": start,
            "end": end,
            "duration": clip_duration,
        }

    def _worker(self, segments, output_path):
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="media_suite_edit_")

            if len(segments) == 1:
                ok = self._export_segment(segments[0], output_path, step_index=0, total_steps=1)
                if not ok:
                    if self.cancel_requested:
                        self.ui_queue.put(("canceled", "Edicao cancelada."))
                    return
            else:
                temp_segments = []
                total_steps = len(segments) + 1
                for index, segment in enumerate(segments, start=1):
                    temp_path = os.path.join(temp_dir, f"segmento_{index}.mp4")
                    ok = self._export_segment(segment, temp_path, step_index=index - 1, total_steps=total_steps)
                    if not ok:
                        if self.cancel_requested:
                            self.ui_queue.put(("canceled", "Edicao cancelada."))
                        return
                    temp_segments.append(temp_path)

                list_path = os.path.join(temp_dir, "concat.txt")
                with open(list_path, "w", encoding="utf-8") as concat_file:
                    for temp_path in temp_segments:
                        normalized_path = temp_path.replace("\\", "/")
                        concat_file.write(f"file '{normalized_path}'\n")

                self.ui_queue.put(("status", "Juntando trechos..."))
                self.ui_queue.put(("progress", 92))
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    list_path,
                    "-c",
                    "copy",
                    output_path,
                ]
                if not self._run_ffmpeg_command(cmd):
                    if self.cancel_requested:
                        self.ui_queue.put(("canceled", "Edicao cancelada."))
                    return

            self.ui_queue.put(("done", {"message": "Video gerado com sucesso.", "last_output": output_path}))
        except FileNotFoundError:
            self.ui_queue.put(("error", "Nao encontrei ffmpeg/ffprobe. Instale-os e adicione ao PATH."))
        except Exception as exc:
            self.ui_queue.put(("error", f"Erro na edicao: {exc}"))
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            self.proc = None
            self.is_running = False

    def _export_segment(self, segment, output_path, step_index, total_steps):
        source = segment["path"]
        start = segment["start"]
        end = segment["end"]
        clip_duration = segment["duration"]

        status_name = os.path.basename(source)
        self.ui_queue.put(("status", f"Processando trecho: {status_name}"))

        cmd = ["ffmpeg", "-y"]
        if start is not None:
            cmd.extend(["-ss", str(start)])
        cmd.extend(["-i", source])

        if end is not None:
            duration_value = end - (start or 0)
            cmd.extend(["-t", str(duration_value)])

        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                output_path,
            ]
        )
        return self._run_ffmpeg_command(cmd, step_index=step_index, total_steps=total_steps, expected_duration=clip_duration)

    def _run_ffmpeg_command(self, cmd, step_index=0, total_steps=1, expected_duration=None):
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=create_no_window_flags(),
        )

        for line in self.proc.stderr:
            if self.cancel_requested:
                break
            if "time=" not in line or not expected_duration or expected_duration <= 0:
                continue
            try:
                raw_time = line.split("time=")[1].split(" ")[0]
                hours, minutes, seconds = raw_time.split(":")
                current_seconds = float(hours) * 3600 + float(minutes) * 60 + float(seconds)
                fraction = max(0.0, min(1.0, current_seconds / expected_duration))
                pct = ((step_index + fraction) / max(total_steps, 1)) * 100.0
                self.ui_queue.put(("progress", pct))
            except Exception:
                continue

        return_code = self.proc.wait()

        if self.cancel_requested:
            try:
                if os.path.exists(output_path := cmd[-1]):
                    os.remove(output_path)
            except Exception:
                pass
            return False

        if return_code != 0:
            self.ui_queue.put(("error", f"Falha ao processar: {os.path.basename(cmd[-1])}"))
            return False

        self.ui_queue.put(("progress", ((step_index + 1) / max(total_steps, 1)) * 100.0))
        return True

    def _probe_duration(self, path):
        try:
            output = subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", path],
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=create_no_window_flags(),
                stderr=subprocess.DEVNULL,
            )
            return float(output.strip())
        except Exception:
            return None

    def _duration_text(self, path):
        duration = self.file_durations.get(path)
        if duration is None:
            return "Duracao nao encontrada"
        return f"Duracao: {seconds_to_hms(duration)}"

    def _drain_ui_queue(self):
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()

                if kind == "progress":
                    self.progress_var.set(float(payload))
                elif kind == "status":
                    self.status_var.set(str(payload))
                    self.on_status(str(payload))
                elif kind == "done":
                    info = payload if isinstance(payload, dict) else {"message": str(payload)}
                    self.last_output = info.get("last_output") or ""
                    message = info.get("message", "Video gerado com sucesso.")
                    self._finish_ok(message)
                elif kind == "canceled":
                    self._finish_canceled(payload)
                elif kind == "error":
                    self._finish_error(payload)
        except queue.Empty:
            pass
        finally:
            if not self.is_running and self.cancel_btn["state"] == NORMAL:
                self._update_action_state()
            self.after(100, self._drain_ui_queue)

    def open_folder(self):
        if not self.last_output or not os.path.exists(self.last_output):
            messagebox.showerror("Erro", "Nenhum video gerado foi encontrado.")
            return

        folder = os.path.dirname(self.last_output)
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:
            messagebox.showerror("Erro", f"Nao foi possivel abrir a pasta: {exc}")

    def _finish_ok(self, message):
        self._hide_progress()
        self.last_output = self.last_output or ""
        self.progress_var.set(100)
        self.status_var.set(message)
        self.on_status(message)
        self._update_action_state()
        self.open_btn.config(state=NORMAL if self.last_output else DISABLED)
        messagebox.showinfo("Concluido", message)

    def _finish_canceled(self, payload):
        self._hide_progress()
        self.progress_var.set(0)
        self.status_var.set(str(payload))
        self.on_status(str(payload))
        self._update_action_state()
        self.open_btn.config(state=DISABLED)

    def _finish_error(self, payload):
        self._hide_progress()
        self.on_status("Erro na edicao")
        self._update_action_state()
        self.open_btn.config(state=DISABLED)
        messagebox.showerror("Erro", str(payload))
