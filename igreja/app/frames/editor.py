import os
import sys
import queue
import shutil
import tempfile
import threading
import subprocess
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.ui.theme import get_theme_profile
from app.ui.output_folder import OutputFolderMixin
from app.utils import (
    HAS_DND, DND_FILES, create_no_window_flags, ffmpeg_cmd, ffprobe_cmd, seconds_to_hms, _ext,
)


VIDEO_EXTS = {"mp4", "avi", "mkv", "mov", "webm", "flv", "m4v"}
AUDIO_EXTS = {"mp3", "wav", "aac", "flac", "m4a", "wma", "opus", "ogg"}
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS


def is_video_file(path: str) -> bool:
    return _ext(path) in VIDEO_EXTS


def is_audio_file(path: str) -> bool:
    return _ext(path) in AUDIO_EXTS


def is_media_file(path: str) -> bool:
    return _ext(path) in MEDIA_EXTS


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


class EditorFrame(OutputFolderMixin, ttk.Frame):
    def __init__(self, master, on_status):
        super().__init__(master, style="ContentHost.TFrame")
        self.on_status = on_status

        self.input_files = []
        self.file_durations = {}
        self.last_output = ""

        # Dynamically generated UI rows for each selected video (Trecho 1, 2, 3...)
        self.video_rows = []
        self.output_name_var = tk.StringVar()
        self.init_output_folder("Mesma pasta do primeiro arquivo selecionado")

        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="")
        self.is_running = False
        self.cancel_requested = False
        self.proc = None
        self._last_action_key_ts = 0.0
        self.ui_queue = queue.Queue()

        self._build_ui()
        self.bind_all("<Return>", self._handle_return_key, add="+")
        self.bind_all("<Escape>", self._handle_escape_key, add="+")
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
        self.canvas = tk.Canvas(
            self,
            borderwidth=0,
            highlightthickness=0,
            background=self._theme_color("panel_bg"),
        )
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        # Scrollbar is shown only when needed (e.g. after a file is selected).

        self.scrollable_frame = ttk.Frame(self.canvas, style="Card.TFrame")
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

        card = ttk.Frame(self.scrollable_frame, padding=20, style="Card.TFrame")
        card.pack(fill="both", expand=True)

        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Editor de Mídia", style="SectionTitle.TLabel").pack(side="left")
        ttk.Separator(card).pack(fill="x", pady=12)

        files_frame = ttk.Labelframe(card, text="Arquivos", style="Hero.TLabelframe")
        files_frame.pack(fill="x")
        files_inner = ttk.Frame(files_frame, padding=12, style="SurfaceAlt.TFrame")
        files_inner.pack(fill="x")
        files_inner.columnconfigure(1, weight=1)

        ttk.Button(files_inner, text="Selecionar mídia", command=self.select_files, style="PrimaryAction.TButton").grid(
            row=0, column=0, sticky="w"
        )
        self.clear_btn = ttk.Button(files_inner, text="Limpar", command=self.clear_files, style="DangerAction.TButton")
        self.clear_btn.grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Label(
            files_inner,
            text="Monte um novo arquivo usando um trecho de cada arquivo. Use vazio para considerar o arquivo inteiro.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 6))

        self.selection_label = ttk.Label(files_inner, text="Nenhum arquivo selecionado", font=("Helvetica", 12), style="SurfaceAlt.TLabel")
        self.selection_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 6))

        if HAS_DND:
            ttk.Label(
                files_inner,
                text="Arraste e solte arquivos de mídia aqui para selecionar.",
                style="SurfaceMuted.TLabel",
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 6))

        # Container for the list of selected videos (Trecho 1, Trecho 2, ...).
        self.videos_container = ttk.Frame(card, style="Card.TFrame")
        self.videos_container.pack(fill="x", pady=(2, 6))

        # Build initial empty list (no videos selected yet).
        self._rebuild_video_rows()

        options = ttk.Labelframe(card, text="Opções")
        options.pack(fill="x", pady=(2, 6))
        options_inner = ttk.Frame(options, padding=12, style="SurfaceAlt.TFrame")
        options_inner.pack(fill="x")
        options.pack_forget()
        self.options_frame = options
        options_inner.columnconfigure(0, weight=1)
        options_inner.columnconfigure(1, weight=1)

        ttk.Label(options_inner, text="Ordem de montagem", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(options_inner, text="Nome do arquivo final", font=("Segoe UI", 12, "bold")).grid(row=0, column=1, sticky="w")

        ttk.Label(options_inner, text="Seguir a ordem dos vídeos selecionados", font=("Segoe UI", 11)).grid(
            row=1, column=0, sticky="w", padx=(0, 20)
        )
        ttk.Entry(options_inner, textvariable=self.output_name_var, width=28).grid(row=1, column=1, sticky="ew")
        ttk.Label(options_inner, text="Define o nome do video ou audio montado ao final.", style="SurfaceMuted.TLabel").grid(
            row=2, column=1, sticky="w", pady=(6, 0)
        )
        ttk.Button(options_inner, text="Escolher pasta de destino", command=self.choose_dest_folder, style="Action.TButton").grid(
            row=3, column=0, sticky="w", pady=(10, 0)
        )
        self.dest_label = ttk.Label(
            options_inner,
            text=self.get_destination_label_text(),
            style="Muted.TLabel",
        )
        self.dest_label.grid(row=3, column=1, sticky="ew", pady=(10, 0))

        self.controls_frame = ttk.Frame(card, style="Card.TFrame")
        self.controls_frame.pack(fill="x", pady=(2, 6))
        self.run_btn = ttk.Button(self.controls_frame, text="Processar mídia", command=self.start_processing, style="PrimaryAction.TButton", state=DISABLED)
        self.run_btn.pack(side="left")
        self.cancel_btn = ttk.Button(self.controls_frame, text="Cancelar", command=self.cancel_processing, style="Action.TButton", state=DISABLED)
        self.cancel_btn.pack(side="left", padx=(10, 0))
        self.cancel_btn.pack_forget()
        self.open_btn = ttk.Button(self.controls_frame, text="Abrir pasta do arquivo", command=self.open_folder, style="Action.TButton", state=DISABLED)
        self.open_btn.pack(side="left", padx=(10, 0))
        self.controls_frame.pack_forget()

        hint = ttk.Label(
            card,
            text="Formatos de tempo aceitos: 90, 01:30, 00:01:30.500",
            style="CardMuted.TLabel",
        )
        hint.pack(anchor="w", pady=(0, 6))

        self.progress_frame = ttk.Frame(card, padding=(10, 6), style="SurfaceAlt.TFrame")
        self.progress = ttk.Progressbar(self.progress_frame, orient=tk.HORIZONTAL, mode="determinate", variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x")
        ttk.Label(self.progress_frame, textvariable=self.status_var, font=("Helvetica", 11)).pack(anchor="w", pady=(6, 0))

        # Hide progress UI until processing starts.
        self._hide_progress()

        self._update_action_state()
        self._update_visibility()

    def select_files(self):
        filetypes = [
            ("Mídia (Vídeos/Áudios)", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.m4v *.mp3 *.wav *.aac *.flac *.m4a *.wma *.opus *.ogg"),
            ("Vídeos", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.m4v"),
            ("Áudios", "*.mp3 *.wav *.aac *.flac *.m4a *.wma *.opus *.ogg"),
            ("Todos", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="Selecione arquivos de mídia", filetypes=filetypes)
        if paths:
            self._set_files(list(paths), append=True)

    def _on_drop_files(self, event):
        items = self.tk.splitlist(event.data)
        paths = []
        for item in items:
            if os.path.isfile(item) and is_media_file(item):
                paths.append(os.path.abspath(item))
        if paths:
            self._set_files(paths, append=True)

    def _set_files(self, paths, append=False):
        existing_files = list(self.input_files) if append else []
        uniq = []
        seen = set()
        for path in [*existing_files, *paths]:
            abs_path = os.path.abspath(path)
            if not os.path.isfile(abs_path) or not is_media_file(abs_path):
                continue
            low = abs_path.lower()
            if low in seen:
                continue
            seen.add(low)
            uniq.append(abs_path)

        if not uniq:
            return

        self.input_files = uniq
        self.file_durations = {path: self._probe_duration(path) for path in uniq}
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
            self.selection_label.config(text="Nenhum arquivo selecionado")
            self._rebuild_video_rows()
            self._update_visibility()
            return

        count = len(self.input_files)
        if count == 1:
            self.selection_label.config(text=f"1 arquivo selecionado: {os.path.basename(self.input_files[0])}")
        else:
            self.selection_label.config(
                text=f"{count} arquivos selecionados: {os.path.basename(self.input_files[0])} + {os.path.basename(self.input_files[1])}"
            )

        self._rebuild_video_rows()
        self._update_visibility()
        # Ensure the action buttons are visible after selecting a file in smaller windows.
        self._scroll_to_bottom()
        self._update_scrollbar_visibility()

    def _rebuild_video_rows(self):
        """Rebuild the per-media segment editors (Trecho 1, Trecho 2, ...)."""
        # Clear existing rows
        for row in self.video_rows:
            try:
                row["frame"].destroy()
            except Exception:
                pass
        self.video_rows = []

        for idx, path in enumerate(self.input_files, start=1):
            row_frame = ttk.Labelframe(self.videos_container, text=f"Trecho {idx}")
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
                style="DangerAction.TButton",
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
        
        # Determina se é áudio ou vídeo pelo primeiro arquivo
        first_file = self.input_files[0]
        is_audio = is_audio_file(first_file)
        
        if len(self.input_files) == 1:
            base = os.path.splitext(os.path.basename(first_file))[0]
            if is_audio:
                self.output_name_var.set(f"{base}_editado.mp3")
            else:
                self.output_name_var.set(f"{base}_editado.mp4")
            return
        
        if is_audio:
            self.output_name_var.set("audio_montado.mp3")
        else:
            self.output_name_var.set("video_montado.mp4")

    def _update_visibility(self):
        """Show/hide the editor sections depending on whether any file is selected."""
        if self.input_files:
            self.clear_btn.grid()
            if not self.videos_container.winfo_ismapped():
                self.videos_container.pack(fill="x", pady=(2, 6))
            if not self.options_frame.winfo_ismapped():
                self.options_frame.pack(fill="x", pady=(2, 6))
            if not self.controls_frame.winfo_ismapped():
                self.controls_frame.pack(fill="x", pady=(2, 6))
            if self.is_running:
                if not self.cancel_btn.winfo_ismapped():
                    self.cancel_btn.pack(side="left", padx=(10, 0))
            elif self.cancel_btn.winfo_ismapped():
                self.cancel_btn.pack_forget()
            if self.last_output and not self.open_btn.winfo_ismapped():
                self.open_btn.pack(side="left", padx=(10, 0))
            elif not self.last_output and self.open_btn.winfo_ismapped():
                self.open_btn.pack_forget()
        else:
            self.clear_btn.grid_remove()
            self.videos_container.pack_forget()
            self.options_frame.pack_forget()
            self.controls_frame.pack_forget()
            self.cancel_btn.pack_forget()

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
        # Recalcula a area rolavel sempre que o conteudo muda.
        if not getattr(self, "canvas", None):
            return
        try:
            canvas_height = self.canvas.winfo_height()
            target_height = canvas_height if event.height < canvas_height else event.height
            self.canvas.itemconfig(self.scroll_window, height=target_height)
        except Exception:
            pass
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_scrollbar_visibility()

    def _on_canvas_configure(self, event):
        # Mantem a largura sincronizada e so estica a altura quando faltar conteudo.
        try:
            requested_height = self.scrollable_frame.winfo_reqheight()
            target_height = event.height if requested_height < event.height else requested_height
            self.canvas.itemconfig(self.scroll_window, width=event.width, height=target_height)
        except Exception:
            pass
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_scrollbar_visibility()

    def _on_mousewheel(self, event):
        if not getattr(self, "canvas", None):
            return
        if self.canvas.yview() == (0.0, 1.0):
            return
        delta = int(-1 * (event.delta / 120)) if hasattr(event, "delta") else 0
        if delta:
            self.canvas.yview_scroll(delta, "units")
            return "break"

    def _update_scrollbar_visibility(self):
        if not getattr(self, "canvas", None):
            return
        try:
            self.update_idletasks()
        except Exception:
            pass
        bbox = self.canvas.bbox("all")
        if not bbox:
            self.scrollbar.pack_forget()
            self.canvas.configure(yscrollcommand=None)
            return
        content_height = bbox[3] - bbox[1]
        visible_height = self.canvas.winfo_height()
        needs_scroll = bool(self.input_files)
        if needs_scroll:
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(side="right", fill="y")
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
        else:
            self.scrollbar.pack_forget()
            self.canvas.configure(yscrollcommand=None)

    def _is_active_screen(self):
        top = self.winfo_toplevel()
        return getattr(top, "current_screen", None) == getattr(self, "screen_key", None)

    def _handle_return_key(self, event=None):
        if not self._is_active_screen() or self.is_running or str(self.run_btn["state"]) != str(NORMAL):
            return
        if isinstance(event.widget, tk.Text):
            return
        now = time.monotonic()
        if now - self._last_action_key_ts < 0.35:
            return "break"
        self._last_action_key_ts = now
        self.start_processing()
        return "break"

    def _handle_escape_key(self, _event=None):
        if not self._is_active_screen() or not self.is_running:
            return
        self.cancel_processing()
        return "break"

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
            messagebox.showerror("Erro", "Selecione pelo menos um arquivo de mídia.")
            return

        segments = self._build_segments()
        if not segments:
            return

        output_name = (self.output_name_var.get() or "").strip()
        if not output_name:
            messagebox.showerror("Erro", "Informe um nome para o arquivo de saída.")
            return
        
        # Determina extensão esperada baseado no tipo de mídia
        first_file = self.input_files[0]
        is_audio = is_audio_file(first_file)
        expected_ext = ".mp3" if is_audio else ".mp4"
        
        if not output_name.lower().endswith(expected_ext):
            output_name += expected_ext

        output_dir = self.resolve_output_dir(self.input_files[0])
        output_path = os.path.join(output_dir, output_name)
        try:
            self.ensure_output_dir(self.input_files[0])
        except Exception as exc:
            messagebox.showerror("Erro", f"Nao foi possivel preparar a pasta de destino:\n{exc}")
            return
        normalized_output = os.path.abspath(output_path).lower()
        if normalized_output in {os.path.abspath(path).lower() for path in self.input_files}:
            messagebox.showerror("Erro", "Escolha um nome diferente do arquivo original para evitar sobrescrita.")
            return

        self.is_running = True
        self.cancel_requested = False
        self.progress_var.set(0)
        self.status_var.set("Preparando...")
        self.on_status("Processamento iniciado...")
        self.run_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.open_btn.config(state=DISABLED)
        self._show_progress()
        self._update_action_state()
        self._update_visibility()

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
            messagebox.showerror("Erro", "Selecione pelo menos um arquivo de mídia.")
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
            messagebox.showerror("Erro", "Não foi possível montar os trechos selecionados.")
            return None

        return result

    def _build_single_segment(self, path, start_value, end_value, label):
        start = parse_time_to_seconds(start_value)
        end = parse_time_to_seconds(end_value)

        if start_value.strip() and start is None:
            messagebox.showerror("Tempo inválido", f"{label}: início inválido.")
            return None
        if end_value.strip() and end is None:
            messagebox.showerror("Tempo inválido", f"{label}: fim inválido.")
            return None
        if start is not None and start < 0:
            messagebox.showerror("Tempo inválido", f"{label}: o início não pode ser negativo.")
            return None
        if end is not None and end < 0:
            messagebox.showerror("Tempo inválido", f"{label}: o fim não pode ser negativo.")
            return None
        if start is not None and end is not None and end <= start:
            messagebox.showerror("Tempo inválido", f"{label}: o fim precisa ser maior que o início.")
            return None

        duration = self.file_durations.get(path)
        if duration is not None:
            if start is not None and start > duration:
                messagebox.showerror("Tempo inválido", f"{label}: o início ultrapassa a duração do arquivo.")
                return None
            if end is not None and end > duration:
                messagebox.showerror("Tempo inválido", f"{label}: o fim ultrapassa a duração do arquivo.")
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
                        self.ui_queue.put(("canceled", "Processamento cancelado."))
                    return
            else:
                temp_segments = []
                total_steps = len(segments) + 1
                for index, segment in enumerate(segments, start=1):
                    # Determina extensão baseada no tipo de mídia
                    is_audio = is_audio_file(segment["path"])
                    ext = "mp3" if is_audio else "mp4"
                    temp_path = os.path.join(temp_dir, f"segmento_{index}.{ext}")
                    ok = self._export_segment(segment, temp_path, step_index=index - 1, total_steps=total_steps)
                    if not ok:
                        if self.cancel_requested:
                            self.ui_queue.put(("canceled", "Processamento cancelado."))
                        return
                    temp_segments.append(temp_path)

                list_path = os.path.join(temp_dir, "concat.txt")
                with open(list_path, "w", encoding="utf-8") as concat_file:
                    for temp_path in temp_segments:
                        normalized_path = temp_path.replace("\\", "/")
                        concat_file.write(f"file '{normalized_path}'\n")

                self.ui_queue.put(("status", "Juntando trechos..."))
                self.ui_queue.put(("progress", 92))
                cmd = ffmpeg_cmd(
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
                )
                if not self._run_ffmpeg_command(cmd):
                    if self.cancel_requested:
                        self.ui_queue.put(("canceled", "Processamento cancelado."))
                    return

            self.ui_queue.put(("done", {"message": "Arquivo processado com sucesso.", "last_output": output_path}))
        except FileNotFoundError:
            self.ui_queue.put(("error", "Não encontrei ffmpeg/ffprobe no executável nem no PATH."))
        except Exception as exc:
            self.ui_queue.put(("error", f"Erro no processamento: {exc}"))
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

        cmd = ffmpeg_cmd("-y")
        if start is not None:
            cmd.extend(["-ss", str(start)])
        cmd.extend(["-i", source])

        if end is not None:
            duration_value = end - (start or 0)
            cmd.extend(["-t", str(duration_value)])

        # Detecta tipo de mídia
        is_audio = is_audio_file(source)
        
        if is_audio:
            # Configuração para áudio MP3
            cmd.extend(
                [
                    "-q:a",
                    "3",  # Qualidade MP3 (3 é boa qualidade, 0 é máxima)
                    "-y",
                    output_path,
                ]
            )
        else:
            # Configuração para vídeo MP4
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
                ffprobe_cmd("-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", path),
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
            return "Duração não encontrada"
        return f"Duração: {seconds_to_hms(duration)}"

    def _theme_color(self, key):
        top = self.winfo_toplevel()
        mode = getattr(top, "theme_var", None)
        profile = get_theme_profile(mode)
        return profile[key]

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
                    message = info.get("message", "Arquivo processado com sucesso.")
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
            if self.winfo_exists():
                self.after(100, self._drain_ui_queue)

    def open_folder(self):
        if not self.last_output or not os.path.exists(self.last_output):
            messagebox.showerror("Erro", "Nenhum arquivo processado foi encontrado.")
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
            messagebox.showerror("Erro", f"Não foi possível abrir a pasta: {exc}")

    def _finish_ok(self, message):
        self._hide_progress()
        self.last_output = self.last_output or ""
        self.progress_var.set(100)
        self.status_var.set(message)
        self.on_status(message)
        self._update_action_state()
        self.open_btn.config(state=NORMAL if self.last_output else DISABLED)
        self._update_visibility()
        messagebox.showinfo("Concluído", message)

    def _finish_canceled(self, payload):
        self._hide_progress()
        self.progress_var.set(0)
        self.status_var.set(str(payload))
        self.on_status(str(payload))
        self._update_action_state()
        self.open_btn.config(state=DISABLED)
        self._update_visibility()

    def _finish_error(self, payload):
        self._hide_progress()
        self.on_status("Erro no processamento")
        self._update_action_state()
        self.open_btn.config(state=DISABLED)
        self._update_visibility()
        messagebox.showerror("Erro", str(payload))
