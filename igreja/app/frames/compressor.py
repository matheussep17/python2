import os
import sys
import queue
import threading
import subprocess
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.ui.output_folder import OutputFolderMixin
from app.utils import (
    HAS_DND,
    HAS_PIL,
    DND_FILES,
    Image,
    create_no_window_flags,
    ffmpeg_cmd,
    ffprobe_cmd,
    seconds_to_hms,
    _ext,
)


VIDEO_EXTS = {"mp4", "avi", "mkv", "mov", "webm", "flv", "m4v"}
AUDIO_EXTS = {"mp3", "wav", "m4a", "aac", "flac", "opus", "ogg", "wma"}
IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"}
ALL_EXTS = VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS


def is_video_file(path: str) -> bool:
    return _ext(path) in VIDEO_EXTS


def is_audio_file(path: str) -> bool:
    return _ext(path) in AUDIO_EXTS


def is_image_file(path: str) -> bool:
    return _ext(path) in IMAGE_EXTS


class CompressorFrame(OutputFolderMixin, ttk.Frame):
    def __init__(self, master, on_status):
        super().__init__(master)
        self.on_status = on_status

        self.input_files = []
        self.last_output = ""
        self.output_name_var = tk.StringVar()
        self.init_output_folder("Mesma pasta do arquivo original")

        self.video_preset = tk.StringVar(value="Equilibrado")
        self.audio_bitrate = tk.StringVar(value="128 kbps")
        self.image_quality = tk.StringVar(value="75")

        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="")
        self.is_running = False
        self.cancel_requested = False
        self.proc = None
        self.current_mode = None
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
        card = ttk.Frame(self, padding=20, style="Card.TFrame")
        card.pack(fill="both", expand=True)

        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Compressor de Video / Audio / Foto", style="SectionTitle.TLabel").pack(side="left")
        ttk.Separator(card).pack(fill="x", pady=12)

        # --- Arquivos ---
        files_frame = ttk.Labelframe(card, text="Arquivos", style="Hero.TLabelframe")
        files_frame.pack(fill="x")
        files_inner = ttk.Frame(files_frame, padding=12, style="SurfaceAlt.TFrame")
        files_inner.pack(fill="x")
        files_inner.columnconfigure(1, weight=1)

        ttk.Button(files_inner, text="Selecionar Arquivo(s)", command=self.select_files, style="PrimaryAction.TButton").grid(
            row=0, column=0, sticky="w"
        )
        self.btn_remove = ttk.Button(files_inner, text="Remover", command=self.clear_files, style="DangerAction.TButton")
        self.btn_remove.grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.label_selected = ttk.Label(files_inner, text="Nenhum arquivo selecionado", font=("Helvetica", 12), style="SurfaceAlt.TLabel")
        self.label_selected.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.label_mode = ttk.Label(files_inner, text="", font=("Helvetica", 12), style="SurfaceMuted.TLabel")
        self.label_mode.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        if HAS_DND:
            ttk.Label(
                files_inner,
                text="Arraste e solte videos, audios ou imagens aqui para selecionar.",
                style="SurfaceMuted.TLabel",
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 4))

        # --- Opções ---
        self.opts_frame = ttk.Labelframe(card, text="Opções")
        self.opts_frame.pack(fill="x", pady=(10, 0))
        opts_inner = ttk.Frame(self.opts_frame, padding=12, style="SurfaceAlt.TFrame")
        opts_inner.pack(fill="x")
        opts_inner.columnconfigure(1, weight=1)

        self.video_opts = ttk.Frame(opts_inner, style="SurfaceAlt.TFrame")
        self.video_opts.columnconfigure(1, weight=1)
        ttk.Label(self.video_opts, text="Compressao de video:", font=("Helvetica", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.video_menu = ttk.Combobox(
            self.video_opts,
            textvariable=self.video_preset,
            values=["Maxima compressao", "Economico", "Equilibrado", "Alta qualidade"],
            state="readonly",
            width=16,
        )
        self.video_menu.grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.audio_opts = ttk.Frame(opts_inner, style="SurfaceAlt.TFrame")
        self.audio_opts.columnconfigure(1, weight=1)
        ttk.Label(self.audio_opts, text="Bitrate do audio:", font=("Helvetica", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.audio_menu = ttk.Combobox(
            self.audio_opts,
            textvariable=self.audio_bitrate,
            values=["192 kbps", "128 kbps", "96 kbps", "64 kbps"],
            state="readonly",
            width=12,
        )
        self.audio_menu.grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.image_opts = ttk.Frame(opts_inner, style="SurfaceAlt.TFrame")
        self.image_opts.columnconfigure(1, weight=1)
        ttk.Label(self.image_opts, text="Qualidade da foto:", font=("Helvetica", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.image_menu = ttk.Combobox(
            self.image_opts,
            textvariable=self.image_quality,
            values=["85", "75", "60", "45"],
            state="readonly",
            width=8,
        )
        self.image_menu.grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.output_row = ttk.Frame(self.opts_frame, style="SurfaceAlt.TFrame")
        self.output_row.columnconfigure(1, weight=1)
        self.output_row.pack(fill="x", pady=(10, 0))
        ttk.Label(self.output_row, text="Nome do arquivo:", font=("Helvetica", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.output_name_entry = ttk.Entry(self.output_row, textvariable=self.output_name_var, width=32)
        self.output_name_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        ttk.Label(self.output_row, text="Editavel quando houver 1 arquivo selecionado.", style="SurfaceMuted.TLabel").grid(
            row=0, column=2, sticky="w", padx=(10, 0)
        )
        self.output_name_entry.configure(state=DISABLED)

        self.dest_row = ttk.Frame(self.opts_frame, style="SurfaceAlt.TFrame")
        self.dest_row.columnconfigure(1, weight=1)
        self.dest_row.pack(fill="x", pady=(10, 0))
        ttk.Button(self.dest_row, text="Escolher pasta de destino", command=self.choose_dest_folder, style="Action.TButton").grid(
            row=0, column=0, sticky="w"
        )
        self.dest_label = ttk.Label(
            self.dest_row,
            text=self.get_destination_label_text(),
            style="SurfaceMuted.TLabel",
        )
        self.dest_label.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        # --- Acoes ---
        self.controls_frame = ttk.Frame(card, style="Card.TFrame")
        self.controls_frame.pack(fill="x", pady=(12, 6))
        self.btn_run = ttk.Button(self.controls_frame, text="Comprimir", command=self.start_compression, style="PrimaryAction.TButton", state=DISABLED)
        self.btn_run.pack(side="left")
        self.btn_cancel = ttk.Button(self.controls_frame, text="Cancelar", command=self.cancel, style="Action.TButton", state=DISABLED)
        self.btn_cancel.pack(side="left", padx=(10, 0))
        self.btn_cancel.pack_forget()
        self.controls_frame.pack_forget()

        self.progress_frame = ttk.Frame(card, padding=10, style="SurfaceAlt.TFrame")
        self.progress = ttk.Progressbar(self.progress_frame, orient=tk.HORIZONTAL, mode="determinate", variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x")
        self.status_lbl = ttk.Label(self.progress_frame, textvariable=self.status_var, font=("Helvetica", 11), style="SurfaceAlt.TLabel")
        self.status_lbl.pack(anchor="w", pady=(6, 0))

        # Hide progress UI until compression starts
        self._hide_progress()

        self.btn_open = ttk.Button(card, text="Abrir pasta do arquivo", command=self.open_folder, style="Action.TButton", state=DISABLED)
        self.btn_open.pack(pady=8)
        self.btn_open.pack_forget()
        self._update_action_state()
        self._update_visibility()

    def select_files(self):
        filetypes = [
            ("Videos, audios e imagens", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.m4v *.mp3 *.wav *.m4a *.aac *.flac *.opus *.ogg *.wma *.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
            ("Videos", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.m4v"),
            ("Audios", "*.mp3 *.wav *.m4a *.aac *.flac *.opus *.ogg *.wma"),
            ("Imagens", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
            ("Todos", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="Selecione arquivo(s)", filetypes=filetypes)
        if paths:
            self._set_files(list(paths))

    def _on_drop_files(self, event):
        items = self.tk.splitlist(event.data)
        paths = []
        for it in items:
            if os.path.isfile(it) and _ext(it) in ALL_EXTS:
                paths.append(os.path.abspath(it))
            elif os.path.isdir(it):
                try:
                    for nm in os.listdir(it):
                        fp = os.path.join(it, nm)
                        if os.path.isfile(fp) and _ext(fp) in ALL_EXTS:
                            paths.append(os.path.abspath(fp))
                except Exception:
                    pass
        if paths:
            self._set_files(paths)

    def _set_files(self, paths):
        uniq = []
        seen = set()
        for p in paths:
            low = os.path.abspath(p).lower()
            if low not in seen and os.path.isfile(p) and _ext(p) in ALL_EXTS:
                seen.add(low)
                uniq.append(os.path.abspath(p))
        self.input_files = uniq

        if not uniq:
            self.label_selected.config(text="Nenhum arquivo selecionado")
            self.label_mode.config(text="")
            self._apply_mode(None)
            self._refresh_output_name()
            return

        all_video = all(is_video_file(p) for p in uniq)
        all_audio = all(is_audio_file(p) for p in uniq)
        all_image = all(is_image_file(p) for p in uniq)
        if not (all_video or all_audio or all_image):
            messagebox.showerror("Selecao invalida", "Selecione apenas videos, audios ou apenas imagens.")
            self.input_files = []
            self.label_selected.config(text="Nenhum arquivo selecionado")
            self.label_mode.config(text="")
            self._apply_mode(None)
            self._refresh_output_name()
            return

        self.current_mode = "video" if all_video else "audio" if all_audio else "image"
        if len(uniq) == 1:
            self.label_selected.config(text=f"Arquivo: {os.path.basename(uniq[0])}")
        else:
            self.label_selected.config(text=f"{len(uniq)} arquivos (ex.: {os.path.basename(uniq[0])})")
        mode_label = "Video" if self.current_mode == "video" else "Audio" if self.current_mode == "audio" else "Imagem"
        self.label_mode.config(text=f"Modo: {mode_label}")
        self._apply_mode(self.current_mode)
        self._refresh_output_name()
        self._update_action_state()
        self._update_visibility()

    def _apply_mode(self, mode):
        self.video_opts.pack_forget()
        self.audio_opts.pack_forget()
        self.image_opts.pack_forget()
        if mode == "video":
            self.video_opts.pack(fill="x", pady=(10, 0))
        elif mode == "audio":
            self.audio_opts.pack(fill="x", pady=(10, 0))
        elif mode == "image":
            self.image_opts.pack(fill="x", pady=(10, 0))

    def _refresh_output_name(self):
        if not self.input_files:
            self.output_name_var.set("")
            self.output_name_entry.configure(state=DISABLED)
            return

        if len(self.input_files) > 1:
            self.output_name_var.set("")
            self.output_name_entry.configure(state=DISABLED)
            return

        base, ext = os.path.splitext(os.path.basename(self.input_files[0]))
        if self.current_mode == "audio":
            ext = ".mp3"
        self.output_name_var.set(f"{base}_compactado{ext}")
        self.output_name_entry.configure(state=NORMAL)

    def _is_active_screen(self):
        top = self.winfo_toplevel()
        return getattr(top, "current_screen", None) == getattr(self, "screen_key", None)

    def _handle_return_key(self, event=None):
        if not self._is_active_screen() or self.is_running or str(self.btn_run["state"]) != str(NORMAL):
            return
        if isinstance(event.widget, tk.Text):
            return
        now = time.monotonic()
        if now - self._last_action_key_ts < 0.35:
            return "break"
        self._last_action_key_ts = now
        self.start_compression()
        return "break"

    def _handle_escape_key(self, _event=None):
        if not self._is_active_screen() or not self.is_running:
            return
        self.cancel()
        return "break"

    def _update_action_state(self):
        if self.is_running:
            self.btn_run.config(state=DISABLED)
            self.btn_cancel.config(state=NORMAL)
            return

        self.btn_run.config(state=NORMAL if self.input_files else DISABLED)
        self.btn_cancel.config(state=DISABLED)

    def _update_visibility(self):
        """Show/hide options and controls depending on file selection."""
        if self.input_files:
            self.btn_remove.grid()
            if not self.opts_frame.winfo_ismapped():
                self.opts_frame.pack(fill="x", pady=(10, 0))
            if not self.controls_frame.winfo_ismapped():
                self.controls_frame.pack(fill="x", pady=(12, 6))
            if self.is_running:
                if not self.btn_cancel.winfo_ismapped():
                    self.btn_cancel.pack(side="left", padx=(10, 0))
            elif self.btn_cancel.winfo_ismapped():
                self.btn_cancel.pack_forget()
            if self.last_output and not self.btn_open.winfo_ismapped():
                self.btn_open.pack(pady=8)
            elif not self.last_output and self.btn_open.winfo_ismapped():
                self.btn_open.pack_forget()
        else:
            self.btn_remove.grid_remove()
            self.opts_frame.pack_forget()
            self.controls_frame.pack_forget()
            self.btn_cancel.pack_forget()
            self.btn_open.pack_forget()

        # Only show progress while compression is running.
        if self.is_running:
            self._show_progress()
        else:
            self._hide_progress()

    def _show_progress(self):
        if getattr(self, "progress_frame", None) and not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill="x", pady=(8, 4))

    def _hide_progress(self):
        if getattr(self, "progress_frame", None) and self.progress_frame.winfo_ismapped():
            self.progress_frame.pack_forget()

    def clear_files(self):
        self.input_files = []
        self.current_mode = None
        self.label_selected.config(text="Nenhum arquivo selecionado")
        self.label_mode.config(text="")
        self.progress_var.set(0)
        self.status_var.set("")
        self._hide_progress()
        self.last_output = ""
        self.btn_open.config(state=DISABLED)
        self.output_name_var.set("")
        self.output_name_entry.configure(state=DISABLED)
        self._apply_mode(None)
        self._update_action_state()
        self._update_visibility()

    def start_compression(self):
        if self.is_running:
            return
        if not self.input_files:
            messagebox.showerror("Erro", "Selecione arquivo(s) primeiro.")
            return

        all_video = all(is_video_file(p) for p in self.input_files)
        all_audio = all(is_audio_file(p) for p in self.input_files)
        all_image = all(is_image_file(p) for p in self.input_files)
        if not (all_video or all_audio or all_image):
            messagebox.showerror("Selecao invalida", "Selecione apenas videos, audios ou apenas imagens.")
            return

        if all_image and (not HAS_PIL or Image is None):
            messagebox.showerror("Dependencias", "Compressao de imagens requer Pillow. Instale: pip install pillow")
            return

        if len(self.input_files) == 1:
            custom_name = (self.output_name_var.get() or "").strip()
            if not custom_name:
                messagebox.showerror("Erro", "Informe um nome para o arquivo de saida.")
                return
            proposed_output = self._build_output_path(self.input_files[0])
            if os.path.abspath(proposed_output).lower() == os.path.abspath(self.input_files[0]).lower():
                messagebox.showerror("Erro", "Escolha um nome diferente do arquivo original.")
                return

        try:
            self.ensure_output_dir(self.input_files[0])
        except Exception as exc:
            messagebox.showerror("Erro", f"Nao foi possivel preparar a pasta de destino:\n{exc}")
            return

        self.current_mode = "video" if all_video else "audio" if all_audio else "image"
        self.is_running = True
        self.cancel_requested = False
        self.btn_run.config(state=DISABLED)
        self.btn_cancel.config(state=NORMAL)
        self.btn_open.config(state=DISABLED)
        self._show_progress()
        self._update_action_state()
        self._update_visibility()
        self.progress_var.set(0)
        self.status_var.set("Preparando...")
        self.on_status("Compressao iniciada...")

        threading.Thread(target=self._batch_worker, args=(self.input_files[:], self.current_mode), daemon=True).start()

    def cancel(self):
        if not self.is_running:
            return
        self.cancel_requested = True
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass

    def _batch_worker(self, files, mode):
        last_out = None
        ok_count = 0
        fail_count = 0
        total = len(files)
        try:
            for idx, in_path in enumerate(files, start=1):
                if self.cancel_requested:
                    break
                out_path = self._build_output_path(in_path)
                self.ui_queue.put(("status", f"[{idx}/{total}] Preparando..."))
                if mode == "video":
                    ok = self._compress_video(in_path, out_path, idx, total)
                elif mode == "audio":
                    ok = self._compress_audio(in_path, out_path, idx, total)
                else:
                    ok = self._compress_image(in_path, out_path, idx, total)
                if ok:
                    ok_count += 1
                    last_out = out_path
                else:
                    fail_count += 1

            if self.cancel_requested:
                self.ui_queue.put(("canceled", "Compressao cancelada."))
            else:
                if fail_count:
                    msg = f"Compressao concluida: {ok_count} de {total}. {fail_count} falharam."
                else:
                    msg = f"Compressao concluida: {ok_count} arquivo(s)."
                self.ui_queue.put(("done", {"message": msg, "last_output": last_out, "successes": ok_count}))
        except Exception as e:
            self.ui_queue.put(("error", f"Erro no processamento: {e}"))
        finally:
            self.is_running = False
            self.proc = None

    def _build_output_path(self, in_path):
        output_dir = self.resolve_output_dir(in_path)
        default_ext = ".mp3" if self.current_mode == "audio" else os.path.splitext(in_path)[1]
        if len(self.input_files) == 1:
            custom_name = (self.output_name_var.get() or "").strip()
            if custom_name:
                if "." not in os.path.basename(custom_name):
                    custom_name += default_ext
                return os.path.join(output_dir, custom_name)

        base, ext = os.path.splitext(in_path)
        if self.current_mode == "audio":
            ext = ".mp3"
        return os.path.join(output_dir, f"{os.path.basename(base)}_compactado{ext}")

    def _video_params(self):
        preset = self.video_preset.get()
        # Tuned for practical size reduction while keeping readability.
        # Lower CRF = better quality / larger output.
        mapping = {
            "Alta qualidade": {"crf": "22", "preset": "slow", "audio_bitrate": "160k"},
            "Equilibrado": {"crf": "25", "preset": "medium", "audio_bitrate": "128k"},
            "Economico": {"crf": "28", "preset": "medium", "audio_bitrate": "112k"},
            "Maxima compressao": {"crf": "31", "preset": "faster", "audio_bitrate": "96k"},
        }
        return mapping.get(preset, mapping["Equilibrado"])

    def _compress_video(self, in_path, out_path, idx, total):
        try:
            duration = self._probe_duration(in_path)
            params = self._video_params()
            cmd = ffmpeg_cmd(
                "-y",
                "-i",
                in_path,
                "-c:v",
                "libx264",
                "-preset",
                params["preset"],
                "-crf",
                params["crf"],
                "-c:a",
                "aac",
                "-b:a",
                params["audio_bitrate"],
                "-movflags",
                "+faststart",
                out_path,
            )

            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                creationflags=create_no_window_flags(),
            )

            total_seconds = float(duration) if duration else None
            for line in self.proc.stderr:
                if self.cancel_requested:
                    break
                if "time=" not in line:
                    continue
                try:
                    t = line.split("time=")[1].split(" ")[0]
                    h, m, s = t.split(":")
                    sec = float(h) * 3600 + float(m) * 60 + float(s)
                    if total_seconds and total_seconds > 0:
                        pct = max(0.0, min(100.0, (sec / total_seconds) * 100.0))
                        self.ui_queue.put(("progress", pct))
                        self.ui_queue.put(
                            ("status", f"[{idx}/{total}] Comprimindo... {pct:.1f}% ({seconds_to_hms(sec)} de {seconds_to_hms(total_seconds)})")
                        )
                except Exception:
                    pass

            ret = self.proc.wait()
            if self.cancel_requested:
                try:
                    if os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                return False
            if ret == 0:
                self.ui_queue.put(("status", f"[{idx}/{total}] Salvo: {os.path.basename(out_path)}"))
                return True
            self.ui_queue.put(("error", f"Falha ao comprimir: {os.path.basename(in_path)}"))
            return False
        except FileNotFoundError:
            self.ui_queue.put(("error", "Nao encontrei ffmpeg/ffprobe no executavel nem no PATH."))
            return False
        except Exception as e:
            self.ui_queue.put(("error", f"Erro no video {os.path.basename(in_path)}: {e}"))
            return False
        finally:
            self.proc = None

    def _compress_audio(self, in_path, out_path, idx, total):
        try:
            duration = self._probe_duration(in_path)
            bitrate = (self.audio_bitrate.get() or "128 kbps").split()[0] + "k"
            cmd = ffmpeg_cmd(
                "-y",
                "-i",
                in_path,
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                bitrate,
                out_path,
            )

            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                creationflags=create_no_window_flags(),
            )

            total_seconds = float(duration) if duration else None
            for line in self.proc.stderr:
                if self.cancel_requested:
                    break
                if "time=" not in line:
                    continue
                try:
                    t = line.split("time=")[1].split(" ")[0]
                    h, m, s = t.split(":")
                    sec = float(h) * 3600 + float(m) * 60 + float(s)
                    if total_seconds and total_seconds > 0:
                        pct = max(0.0, min(100.0, (sec / total_seconds) * 100.0))
                        self.ui_queue.put(("progress", pct))
                        self.ui_queue.put(
                            ("status", f"[{idx}/{total}] Comprimindo audio... {pct:.1f}% ({seconds_to_hms(sec)} de {seconds_to_hms(total_seconds)})")
                        )
                except Exception:
                    pass

            ret = self.proc.wait()
            if self.cancel_requested:
                try:
                    if os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                return False
            if ret == 0:
                self.ui_queue.put(("status", f"[{idx}/{total}] Salvo: {os.path.basename(out_path)}"))
                return True
            self.ui_queue.put(("error", f"Falha ao comprimir audio: {os.path.basename(in_path)}"))
            return False
        except FileNotFoundError:
            self.ui_queue.put(("error", "Nao encontrei ffmpeg/ffprobe no executavel nem no PATH."))
            return False
        except Exception as e:
            self.ui_queue.put(("error", f"Erro no audio {os.path.basename(in_path)}: {e}"))
            return False
        finally:
            self.proc = None

    def _compress_image(self, in_path, out_path, idx, total):
        try:
            quality = int(self.image_quality.get() or "75")
            ext = _ext(in_path)
            self.ui_queue.put(("status", f"[{idx}/{total}] Comprimindo imagem..."))

            with Image.open(in_path) as im:
                save_kwargs = {"optimize": True}
                if ext in ("jpg", "jpeg", "webp"):
                    if ext in ("jpg", "jpeg") and im.mode in ("RGBA", "LA", "P"):
                        im = im.convert("RGB")
                    save_kwargs["quality"] = quality
                elif ext == "png":
                    save_kwargs["compress_level"] = 9 if quality <= 70 else 7

                im.save(out_path, **save_kwargs)

            self.ui_queue.put(("progress", 100))
            self.ui_queue.put(("status", f"[{idx}/{total}] Salvo: {os.path.basename(out_path)}"))
            return True
        except Exception as e:
            self.ui_queue.put(("error", f"Erro na imagem {os.path.basename(in_path)}: {e}"))
            return False

    def _probe_duration(self, path):
        try:
            out = subprocess.check_output(
                ffprobe_cmd("-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", path),
                text=True,
                creationflags=create_no_window_flags(),
                stderr=subprocess.DEVNULL,
            )
            return out.strip()
        except Exception:
            return None

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
                    msg = info.get("message", "Compressao concluida.")
                    self.last_output = info.get("last_output") or ""
                    self._hide_progress()
                    self.status_var.set(msg)
                    self.progress_var.set(100 if int(info.get("successes", 0) or 0) > 0 else 0)
                    self.on_status(msg)
                    self._update_action_state()
                    self.btn_open.config(state=NORMAL if self.last_output else DISABLED)
                    messagebox.showinfo("Conclusao", msg)
                elif kind == "canceled":
                    self._hide_progress()
                    self.status_var.set(str(payload))
                    self.progress_var.set(0)
                    self.on_status(str(payload))
                    self._update_action_state()
                    self.btn_open.config(state=DISABLED)
                elif kind == "error":
                    self.on_status("Erro na compressao")
                    messagebox.showerror("Erro", str(payload))
        except queue.Empty:
            pass
        finally:
            if not self.is_running and self.btn_cancel["state"] == NORMAL:
                self._update_action_state()
            if self.winfo_exists():
                self.after(100, self._drain_ui_queue)

    def open_folder(self):
        if not self.last_output or not os.path.exists(self.last_output):
            messagebox.showerror("Erro", "Nenhum arquivo compactado encontrado.")
            return
        folder = os.path.dirname(self.last_output)
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("Erro", f"Nao foi possivel abrir a pasta: {e}")
