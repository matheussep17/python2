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

        self.segment1_start = tk.StringVar()
        self.segment1_end = tk.StringVar()
        self.segment2_start = tk.StringVar()
        self.segment2_end = tk.StringVar()
        self.sequence_var = tk.StringVar(value="Trecho 1")
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
        card = ttk.Frame(self, padding=18)
        card.pack(fill="both", expand=True)

        header = ttk.Frame(card)
        header.pack(fill="x")
        ttk.Label(header, text="Editor de Video", style="SectionTitle.TLabel").pack(side="left")
        ttk.Separator(card).pack(fill="x", pady=12)

        intro = ttk.Frame(card)
        intro.pack(fill="x")
        ttk.Button(intro, text="Selecionar ate 2 videos", command=self.select_files, bootstyle=WARNING).pack(side="left")
        ttk.Button(intro, text="Limpar", command=self.clear_files, bootstyle=DANGER).pack(side="left", padx=(10, 0))
        ttk.Label(
            card,
            text="Monte um video novo usando um trecho de cada arquivo. Use vazio para considerar o video inteiro.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(8, 6))

        self.selection_label = ttk.Label(card, text="Nenhum video selecionado", font=("Helvetica", 12))
        self.selection_label.pack(anchor="w", pady=(2, 6))

        self.segment1_card = ttk.LabelFrame(card, text="Trecho 1")
        self.segment1_card.pack(fill="x", pady=(2, 6))
        self.file1_label = ttk.Label(self.segment1_card, text="Nenhum video selecionado")
        self.file1_label.grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(6, 2))
        self.file1_duration = ttk.Label(self.segment1_card, text="", style="Muted.TLabel")
        self.file1_duration.grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=(0, 6))
        ttk.Label(self.segment1_card, text="Inicio").grid(row=2, column=0, sticky="w", padx=(10, 6), pady=(0, 8))
        ttk.Entry(self.segment1_card, textvariable=self.segment1_start, width=18).grid(row=2, column=1, sticky="w", pady=(0, 8))
        ttk.Label(self.segment1_card, text="Fim").grid(row=2, column=2, sticky="w", padx=(12, 6), pady=(0, 8))
        ttk.Entry(self.segment1_card, textvariable=self.segment1_end, width=18).grid(row=2, column=3, sticky="w", pady=(0, 8))

        self.segment2_card = ttk.LabelFrame(card, text="Trecho 2")
        self.segment2_card.pack(fill="x", pady=(0, 6))
        self.file2_label = ttk.Label(self.segment2_card, text="Selecione um segundo video para habilitar a montagem")
        self.file2_label.grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(6, 2))
        self.file2_duration = ttk.Label(self.segment2_card, text="", style="Muted.TLabel")
        self.file2_duration.grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=(0, 6))
        ttk.Label(self.segment2_card, text="Inicio").grid(row=2, column=0, sticky="w", padx=(10, 6), pady=(0, 8))
        self.segment2_start_entry = ttk.Entry(self.segment2_card, textvariable=self.segment2_start, width=18)
        self.segment2_start_entry.grid(row=2, column=1, sticky="w", pady=(0, 8))
        ttk.Label(self.segment2_card, text="Fim").grid(row=2, column=2, sticky="w", padx=(12, 6), pady=(0, 8))
        self.segment2_end_entry = ttk.Entry(self.segment2_card, textvariable=self.segment2_end, width=18)
        self.segment2_end_entry.grid(row=2, column=3, sticky="w", pady=(0, 8))

        options = ttk.Frame(card)
        options.pack(fill="x", pady=(2, 6))
        ttk.Label(options, text="Montagem", font=("Helvetica", 13, "bold")).pack(side="left")
        self.sequence_box = ttk.Combobox(
            options,
            textvariable=self.sequence_var,
            values=["Trecho 1"],
            state="readonly",
            width=20,
        )
        self.sequence_box.pack(side="left", padx=(10, 20))
        ttk.Label(options, text="Nome do arquivo", font=("Helvetica", 13, "bold")).pack(side="left")
        ttk.Entry(options, textvariable=self.output_name_var, width=28).pack(side="left", padx=(10, 0))

        ctl = ttk.Frame(card)
        ctl.pack(fill="x", pady=(2, 6))
        self.run_btn = ttk.Button(ctl, text="Gerar video", command=self.start_processing, bootstyle=SUCCESS, state=DISABLED)
        self.run_btn.pack(side="left")
        self.cancel_btn = ttk.Button(ctl, text="Cancelar", command=self.cancel_processing, bootstyle=SECONDARY, state=DISABLED)
        self.cancel_btn.pack(side="left", padx=(10, 0))
        self.open_btn = ttk.Button(ctl, text="Abrir pasta do video", command=self.open_folder, bootstyle=INFO, state=DISABLED)
        self.open_btn.pack(side="left", padx=(10, 0))

        hint = ttk.Label(
            card,
            text="Formatos de tempo aceitos: 90, 01:30, 00:01:30.500",
            style="Muted.TLabel",
        )
        hint.pack(anchor="w", pady=(0, 6))

        prog = ttk.Frame(card, padding=(10, 6))
        prog.pack(fill="x", pady=(4, 2))
        self.progress = ttk.Progressbar(prog, orient=tk.HORIZONTAL, mode="determinate", variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x")
        ttk.Label(prog, textvariable=self.status_var, font=("Helvetica", 11)).pack(anchor="w", pady=(6, 0))

        self._update_action_state()
        self._update_secondary_state()

    def select_files(self):
        filetypes = [
            ("Videos", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.m4v"),
            ("Todos", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="Selecione ate 2 videos", filetypes=filetypes)
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

        if len(uniq) > 2:
            messagebox.showinfo("Limite", "A edicao aceita ate 2 videos por vez. Vou usar os 2 primeiros.")
            uniq = uniq[:2]

        self.input_files = uniq
        self.file_durations = {path: self._probe_duration(path) for path in uniq}
        self.segment1_start.set("")
        self.segment1_end.set("")
        self.segment2_start.set("")
        self.segment2_end.set("")
        self.progress_var.set(0)
        self.status_var.set("")
        self.last_output = ""
        self.open_btn.config(state=DISABLED)

        self._refresh_file_info()
        self._refresh_sequence_options()
        self._refresh_output_name()
        self._update_action_state()

    def _refresh_file_info(self):
        if not self.input_files:
            self.selection_label.config(text="Nenhum video selecionado")
            self.file1_label.config(text="Nenhum video selecionado")
            self.file1_duration.config(text="")
            self.file2_label.config(text="Selecione um segundo video para habilitar a montagem")
            self.file2_duration.config(text="")
            self._update_secondary_state()
            return

        if len(self.input_files) == 1:
            self.selection_label.config(text=f"Video selecionado: {os.path.basename(self.input_files[0])}")
        else:
            self.selection_label.config(
                text=f"2 videos selecionados: {os.path.basename(self.input_files[0])} + {os.path.basename(self.input_files[1])}"
            )

        first = self.input_files[0]
        self.file1_label.config(text=os.path.basename(first))
        self.file1_duration.config(text=self._duration_text(first))

        if len(self.input_files) > 1:
            second = self.input_files[1]
            self.file2_label.config(text=os.path.basename(second))
            self.file2_duration.config(text=self._duration_text(second))
        else:
            self.file2_label.config(text="Selecione um segundo video para habilitar a montagem")
            self.file2_duration.config(text="")

        self._update_secondary_state()

    def _refresh_sequence_options(self):
        if len(self.input_files) > 1:
            values = ["Trecho 1", "Trecho 2", "Trecho 1 + Trecho 2", "Trecho 2 + Trecho 1"]
        else:
            values = ["Trecho 1"]

        self.sequence_box.configure(values=values)
        if self.sequence_var.get() not in values:
            self.sequence_var.set("Trecho 1 + Trecho 2" if len(self.input_files) > 1 else values[0])

    def _refresh_output_name(self):
        if not self.input_files:
            self.output_name_var.set("")
            return
        if len(self.input_files) == 1:
            base = os.path.splitext(os.path.basename(self.input_files[0]))[0]
            self.output_name_var.set(f"{base}_editado.mp4")
            return
        self.output_name_var.set("video_montado.mp4")

    def _update_secondary_state(self):
        has_second = len(self.input_files) > 1
        state = NORMAL if has_second else DISABLED
        self.segment2_start_entry.configure(state=state)
        self.segment2_end_entry.configure(state=state)

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
        self.segment1_start.set("")
        self.segment1_end.set("")
        self.segment2_start.set("")
        self.segment2_end.set("")
        self.output_name_var.set("")
        self.progress_var.set(0)
        self.status_var.set("")
        self.last_output = ""
        self.open_btn.config(state=DISABLED)
        self._refresh_file_info()
        self._refresh_sequence_options()
        self._update_action_state()

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
        segment_map = {}

        first = self._build_single_segment(
            path=self.input_files[0],
            start_value=self.segment1_start.get(),
            end_value=self.segment1_end.get(),
            label="Trecho 1",
        )
        if first is None:
            return None
        segment_map["Trecho 1"] = first

        if len(self.input_files) > 1:
            second = self._build_single_segment(
                path=self.input_files[1],
                start_value=self.segment2_start.get(),
                end_value=self.segment2_end.get(),
                label="Trecho 2",
            )
            if second is None:
                return None
            segment_map["Trecho 2"] = second

        selection = self.sequence_var.get()
        order = [part.strip() for part in selection.split("+")]
        result = []
        for part in order:
            segment = segment_map.get(part)
            if segment:
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
        self.last_output = self.last_output or ""
        self.progress_var.set(100)
        self.status_var.set(message)
        self.on_status(message)
        self._update_action_state()
        self.open_btn.config(state=NORMAL if self.last_output else DISABLED)
        messagebox.showinfo("Concluido", message)

    def _finish_canceled(self, payload):
        self.progress_var.set(0)
        self.status_var.set(str(payload))
        self.on_status(str(payload))
        self._update_action_state()
        self.open_btn.config(state=DISABLED)

    def _finish_error(self, payload):
        self.on_status("Erro na edicao")
        self._update_action_state()
        self.open_btn.config(state=DISABLED)
        messagebox.showerror("Erro", str(payload))
