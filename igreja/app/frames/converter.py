# app/frames/converter.py
import os
import sys
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.utils import (
    HAS_DND, HAS_PIL, HAS_RAWPY, DND_FILES, Image,
    create_no_window_flags, seconds_to_hms, _ext
)

# ---------- Conversor ----------
VIDEO_EXTS = {"mp4", "avi", "mkv", "mov", "webm", "flv", "m4v"}
AUDIO_EXTS = {"wav", "mp3"}
IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff", "cr2"}
ALL_EXTS = VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS


def is_video_file(p): return _ext(p) in VIDEO_EXTS or _ext(p) in AUDIO_EXTS
def is_image_file(p): return _ext(p) in IMAGE_EXTS


class ConverterFrame(ttk.Frame):
    def __init__(self, master, on_status):
        super().__init__(master)
        self.on_status = on_status

        self.input_files = []
        self.ultimo_arquivo_convertido = ""
        self.formato_destino = tk.StringVar(value="mp4")
        self.output_name_var = tk.StringVar()
        self.remove_audio = tk.BooleanVar(value=False)

        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="")
        self.is_converting = False
        self.proc = None
        self.cancel_requested = False
        self._current_output_path = None
        self.ui_queue = queue.Queue()

        self.video_formats = ["mp3", "mp4", "avi", "mkv", "mov", "gif"]
        self.image_formats = ["jpg", "png", "webp", "tiff", "bmp"]
        self.current_mode = "video"

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
        ttk.Label(header, text="Conversor de Video / Imagem", style="SectionTitle.TLabel").pack(side="left")
        ttk.Separator(card).pack(fill="x", pady=12)

        # --- Arquivos ---
        files_frame = ttk.LabelFrame(card, text="Arquivos")
        files_frame.pack(fill="x")
        files_inner = ttk.Frame(files_frame, padding=12)
        files_inner.pack(fill="x")
        files_inner.columnconfigure(1, weight=1)

        ttk.Button(files_inner, text="Selecionar Arquivo(s)", command=self.selecionar_arquivos, bootstyle=WARNING).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(files_inner, text="Remover", command=self.remover_arquivos, bootstyle=DANGER).grid(
            row=0, column=1, sticky="w", padx=(10, 0)
        )

        self.label_video = ttk.Label(files_inner, text="Nenhum arquivo selecionado", font=("Helvetica", 12))
        self.label_video.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.label_formato = ttk.Label(files_inner, text="", font=("Helvetica", 12))
        self.label_formato.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        if HAS_DND:
            ttk.Label(
                files_inner,
                text="Arraste e solte videos/audios (mp4, mkv, mp3...) ou imagens (jpg, png, cr2...)",
                style="Muted.TLabel",
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 4))

        # --- Configuracao de saida ---
        self.opts_frame = ttk.LabelFrame(card, text="Opções")
        self.opts_frame.pack(fill="x", pady=(10, 0))
        opts_inner = ttk.Frame(self.opts_frame, padding=12)
        opts_inner.pack(fill="x")
        opts_inner.columnconfigure(1, weight=1)

        self.fmt_row = ttk.Frame(opts_inner)
        self.fmt_row_visible = False
        self.fmt_row.columnconfigure(1, weight=1)
        ttk.Label(self.fmt_row, text="Converter para:", font=("Helvetica", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.format_menu = ttk.Combobox(self.fmt_row, textvariable=self.formato_destino, values=[], state="readonly", width=14)
        self.format_menu.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.format_menu.bind("<<ComboboxSelected>>", lambda _e: self._refresh_output_name())

        self.audio_row = ttk.Frame(self.opts_frame)
        self.audio_row_visible = False
        self.audio_row.columnconfigure(1, weight=1)
        self.remove_audio_check = ttk.Checkbutton(
            self.audio_row,
            text="Converter sem audio",
            variable=self.remove_audio,
            command=self._on_toggle_remove_audio,
            bootstyle="round-toggle",
        )
        self.remove_audio_check.grid(row=0, column=0, sticky="w")
        ttk.Label(
            self.audio_row,
            text="Mantem o video e remove a trilha sonora no arquivo final.",
            style="Muted.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.output_row = ttk.Frame(self.opts_frame)
        self.output_row.columnconfigure(1, weight=1)
        ttk.Label(self.output_row, text="Nome do arquivo:", font=("Helvetica", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.output_name_entry = ttk.Entry(self.output_row, textvariable=self.output_name_var, width=32)
        self.output_name_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        ttk.Label(self.output_row, text="Editavel quando houver 1 arquivo selecionado.", style="Muted.TLabel").grid(
            row=0, column=2, sticky="w", padx=(10, 0)
        )
        self.output_name_entry.configure(state=DISABLED)

        # --- Acoes ---
        self.controls_frame = ttk.Frame(card)
        self.controls_frame.pack(fill="x", pady=(10, 6))
        self.convert_btn = ttk.Button(self.controls_frame, text="Converter", command=self.start_conversion, bootstyle=SUCCESS, state=DISABLED)
        self.convert_btn.pack(side="left")
        self.cancel_btn = ttk.Button(self.controls_frame, text="Cancelar", command=self.cancel_conversion, bootstyle=SECONDARY, state=DISABLED)
        self.cancel_btn.pack(side="left", padx=(10, 0))
        self.controls_frame.pack_forget()

        self.progress_frame = ttk.Frame(card, padding=10)
        self.progress = ttk.Progressbar(self.progress_frame, orient=tk.HORIZONTAL, mode="determinate", variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x")
        self.status_label = ttk.Label(self.progress_frame, textvariable=self.status_var, font=("Helvetica", 11))
        self.status_label.pack(anchor="w", pady=(6, 0))

        # Hide the progress UI until a conversion is started.
        self._hide_progress()

        self.open_btn = ttk.Button(card, text="Abrir pasta do arquivo convertido", command=self.abrir_pasta, bootstyle=INFO, state=DISABLED)
        self.open_btn.pack(pady=8)
        self.open_btn.pack_forget()
        self._update_action_state()
        self._update_visibility()

    def _show_format_row(self):
        if not self.fmt_row_visible:
            self.fmt_row.pack(fill="x", pady=(8, 5))
            self.fmt_row_visible = True

    def _hide_format_row(self):
        if self.fmt_row_visible:
            self.fmt_row.pack_forget()
            self.fmt_row_visible = False

    def _show_audio_row(self):
        if not self.audio_row_visible:
            self.audio_row.pack(fill="x", pady=(0, 5))
            self.audio_row_visible = True

    def _hide_audio_row(self):
        if self.audio_row_visible:
            self.audio_row.pack_forget()
            self.audio_row_visible = False

    def _input_original_ext(self):
        if len(self.input_files) == 1:
            return _ext(self.input_files[0])
        return ""

    def _can_keep_same_video_format(self):
        original_ext = self._input_original_ext()
        return (
            self.current_mode == "video"
            and self.remove_audio.get()
            and original_ext in self.video_formats
            and original_ext != "mp3"
        )

    def _target_has_no_audio(self, in_path=None, out_ext=None):
        src = _ext(in_path) if in_path else self._input_original_ext()
        dst = (out_ext or self.formato_destino.get() or "").strip().lower()
        if dst == "gif":
            return True
        return self.current_mode == "video" and self.remove_audio.get() and dst != "mp3" and src in VIDEO_EXTS

    def _on_toggle_remove_audio(self):
        self._update_format_menu()
        self._refresh_output_name()

    def _refresh_output_name(self):
        if not self.input_files:
            self.output_name_var.set("")
            self.output_name_entry.configure(state=DISABLED)
            return

        if len(self.input_files) > 1:
            self.output_name_var.set("")
            self.output_name_entry.configure(state=DISABLED)
            return

        in_path = self.input_files[0]
        filename = os.path.splitext(os.path.basename(in_path))[0]
        target_ext = self.formato_destino.get().strip()
        if target_ext:
            original_ext = _ext(in_path)
            if target_ext == original_ext and self._target_has_no_audio(in_path, target_ext):
                filename = f"{filename}_sem_audio"
            self.output_name_var.set(f"{filename}.{target_ext}")
        else:
            self.output_name_var.set(filename)
        self.output_name_entry.configure(state=NORMAL)

    def _next_available_path(self, path: str) -> str:
        """Se o caminho já existe, adiciona sufixo (2), (3), ... até ficar único."""
        if not path:
            return path
        base, ext = os.path.splitext(path)
        if not os.path.exists(path):
            return path

        idx = 2
        while True:
            candidate = f"{base} ({idx}){ext}"
            if not os.path.exists(candidate):
                return candidate
            idx += 1

    def _build_output_path(self, in_path, out_ext):
        original_ext = _ext(in_path)
        filename = os.path.splitext(os.path.basename(in_path))[0]

        output_dir = os.path.dirname(in_path)

        if len(self.input_files) == 1:
            custom_name = (self.output_name_var.get() or "").strip()
            if custom_name:
                if "." not in os.path.basename(custom_name):
                    custom_name = f"{custom_name}.{out_ext}"
                return self._next_available_path(os.path.join(output_dir, custom_name))

        if out_ext == original_ext:
            suffix = "_sem_audio" if self._target_has_no_audio(in_path, out_ext) else "_convertido"
            filename = f"{filename}{suffix}"

        return self._next_available_path(os.path.join(output_dir, filename + f".{out_ext}"))

    def _update_action_state(self):
        if self.is_converting:
            self.convert_btn.config(state=DISABLED)
            self.cancel_btn.config(state=NORMAL)
            return

        has_files = bool(self.input_files)
        has_format = bool(self.formato_destino.get())
        self.convert_btn.config(state=NORMAL if has_files and has_format else DISABLED)
        self.cancel_btn.config(state=DISABLED)

    def _update_visibility(self):
        """Show/hide the options + action area depending on whether files are selected."""
        if self.input_files:
            if not self.opts_frame.winfo_ismapped():
                self.opts_frame.pack(fill="x", pady=(10, 0))
            if not self.controls_frame.winfo_ismapped():
                self.controls_frame.pack(fill="x", pady=(10, 6))
            if not self.open_btn.winfo_ismapped():
                self.open_btn.pack(pady=8)
        else:
            self.opts_frame.pack_forget()
            self.controls_frame.pack_forget()
            self.open_btn.pack_forget()

        # Only show progress when conversion is running.
        if self.is_converting:
            self._show_progress()
        else:
            self._hide_progress()

    def _show_progress(self):
        if getattr(self, "progress_frame", None) and not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill="x", pady=(8, 4))

    def _hide_progress(self):
        if getattr(self, "progress_frame", None) and self.progress_frame.winfo_ismapped():
            self.progress_frame.pack_forget()

    def _update_format_menu(self):
        if not self.input_files:
            self._hide_format_row()
            self._hide_audio_row()
            self.format_menu.config(values=[])
            self._refresh_output_name()
            return

        all_video = all(is_video_file(p) for p in self.input_files)
        all_image = all(is_image_file(p) for p in self.input_files)
        if not (all_video or all_image):
            messagebox.showerror("Selecao invalida", "Selecione apenas VIDEO/AUDIO ou apenas IMAGEM.")
            self._hide_format_row()
            self._hide_audio_row()
            self.format_menu.config(values=[])
            self._refresh_output_name()
            return

        self.current_mode = "image" if all_image else "video"
        if self.current_mode == "video":
            self._show_audio_row()
        else:
            self.remove_audio.set(False)
            self._hide_audio_row()

        values = self.image_formats if self.current_mode == "image" else self.video_formats

        if len(self.input_files) == 1:
            original_ext = _ext(self.input_files[0])
            if original_ext in values and not self._can_keep_same_video_format():
                values = [v for v in values if v != original_ext]

        self.format_menu.config(values=values)
        if self.formato_destino.get() not in values and values:
            self.formato_destino.set(values[0])

        (self._show_format_row() if values else self._hide_format_row())
        self._refresh_output_name()
        self._update_action_state()

    def selecionar_arquivos(self):
        tipos = [
            ("Video/Audio/Imagem", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.m4v *.wav *.mp3 *.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.cr2"),
            ("Videos", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.m4v"),
            ("Audio", "*.wav *.mp3"),
            ("Imagens", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.cr2"),
            ("Todos", "*.*")
        ]
        paths = filedialog.askopenfilenames(title="Selecione arquivo(s)", filetypes=tipos)
        if paths:
            self._set_selected_files(list(paths))

    def _collect_supported_files(self, items):
        out = []
        for it in items:
            if os.path.isfile(it) and _ext(it) in ALL_EXTS:
                out.append(os.path.abspath(it))
            elif os.path.isdir(it):
                try:
                    for nm in os.listdir(it):
                        p = os.path.join(it, nm)
                        if os.path.isfile(p) and _ext(p) in ALL_EXTS:
                            out.append(os.path.abspath(p))
                except Exception:
                    pass

        seen = set()
        uniq = []
        for p in out:
            low = p.lower()
            if low not in seen:
                seen.add(low)
                uniq.append(p)
        return uniq

    def _on_drop_files(self, event):
        items = self.tk.splitlist(event.data)
        if not items:
            return
        paths = self._collect_supported_files(items)
        if paths:
            self._set_selected_files(paths)

    def _set_selected_files(self, caminhos):
        self.input_files = list(caminhos)

        if not self.input_files:
            self.label_video.config(text="Nenhum arquivo selecionado")
            self.label_formato.config(text="")
            self._update_format_menu()
            self._update_visibility()
            return

        if len(self.input_files) == 1:
            f = self.input_files[0]
            self.label_video.config(text=f"Arquivo: {os.path.basename(f)}")
            self.label_formato.config(text=f"Formato original: {_ext(f)}")
        else:
            first = os.path.basename(self.input_files[0])
            self.label_video.config(text=f"{len(self.input_files)} arquivos (ex.: {first})")
            self.label_formato.config(text="Formatos variados")

        self._update_format_menu()
        self._update_visibility()

    def remover_arquivos(self):
        self.input_files = []
        self.label_video.config(text="Nenhum arquivo selecionado")
        self.label_formato.config(text="")
        self.progress_var.set(0)
        self.status_var.set("")
        self._hide_progress()
        self.open_btn.config(state=DISABLED)
        self.current_mode = "video"
        self.formato_destino.set("mp4")
        self.remove_audio.set(False)
        self.output_name_var.set("")
        self.output_name_entry.configure(state=DISABLED)
        self._hide_format_row()
        self._hide_audio_row()
        self.format_menu.config(values=[])
        self._update_action_state()
        self._update_visibility()

    def start_conversion(self):
        if self.is_converting:
            return
        if not self.input_files:
            messagebox.showerror("Erro", "Selecione arquivo(s) primeiro.")
            return

        all_video = all(is_video_file(p) for p in self.input_files)
        all_image = all(is_image_file(p) for p in self.input_files)
        if not (all_video or all_image):
            messagebox.showerror("Selecao invalida", "Selecione apenas VIDEO/AUDIO ou apenas IMAGEM.")
            return

        formato_destino = self.formato_destino.get()
        if not formato_destino:
            messagebox.showerror("Erro", "Selecione um formato de saida.")
            return

        if len(self.input_files) == 1:
            custom_name = (self.output_name_var.get() or "").strip()
            if not custom_name:
                messagebox.showerror("Erro", "Informe um nome para o arquivo de saida.")
                return
            proposed_output = self._build_output_path(self.input_files[0], formato_destino)
            if os.path.abspath(proposed_output).lower() == os.path.abspath(self.input_files[0]).lower():
                messagebox.showerror("Erro", "Escolha um nome diferente do arquivo original.")
                return

        self.is_converting = True
        self.cancel_requested = False
        self._current_output_path = None

        self.convert_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.open_btn.config(state=DISABLED)
        self._show_progress()
        self._update_action_state()

        self.progress_var.set(0)
        self.status_var.set("Preparando...")
        self.on_status("Conversao iniciada...")

        threading.Thread(
            target=self._batch_convert_worker,
            args=(self.input_files[:], formato_destino),
            daemon=True
        ).start()

    def cancel_conversion(self):
        if self.is_converting:
            self.cancel_requested = True
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()
                except Exception:
                    pass

    def _batch_convert_worker(self, files, out_ext):
        try:
            total = len(files)
            last_out = None
            successes = 0
            failures = 0

            for idx, in_path in enumerate(files, start=1):
                if self.cancel_requested:
                    break

                mode = "image" if is_image_file(in_path) and not is_video_file(in_path) else "video"
                out_path = self._build_output_path(in_path, out_ext)
                self._current_output_path = out_path

                self.ui_queue.put(("status", f"[{idx}/{total}] Preparando..."))
                ok = (
                    self._convert_single_image(in_path, out_path, idx, total)
                    if mode == "image"
                    else self._convert_single_video(in_path, out_path, idx, total)
                )
                if not ok:
                    failures += 1
                    if self.cancel_requested:
                        break
                    continue

                successes += 1
                last_out = out_path

            if self.cancel_requested:
                self.ui_queue.put(("canceled", "Conversao cancelada."))
            else:
                if failures:
                    msg = f"Conversao concluida: {successes} de {total} arquivo(s) convertidos. {failures} falharam."
                else:
                    msg = f"Conversao concluida: {successes} arquivo(s) convertidos."
                self.ui_queue.put((
                    "done",
                    {
                        "message": msg,
                        "last_output": last_out,
                        "successes": successes,
                        "failures": failures,
                        "total": total,
                    }
                ))

        except Exception as e:
            if self.cancel_requested:
                self.ui_queue.put(("canceled", "Conversao cancelada."))
            else:
                self.ui_queue.put(("error", f"Erro no processamento: {e}"))
        finally:
            self.proc = None
            self.is_converting = False

    def _convert_single_video(self, in_path, out_path, idx, total):
        try:
            duration = self._probe_duration(in_path)
            total_seconds = float(duration) if duration else None
            out_ext = _ext(out_path)
            remove_audio = self._target_has_no_audio(in_path, out_ext)

            if out_ext == "mp3":
                cmd = ["ffmpeg", "-y", "-i", in_path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", out_path]
            elif out_ext == "gif":
                cmd = ["ffmpeg", "-y", "-i", in_path, "-vf", "fps=12,scale=iw:-1:flags=lanczos", "-loop", "0", out_path]
            elif remove_audio:
                cmd = ["ffmpeg", "-y", "-i", in_path, "-an", out_path]
            else:
                cmd = ["ffmpeg", "-y", "-i", in_path, out_path]

            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=create_no_window_flags()
            )

            for line in self.proc.stderr:
                if self.cancel_requested:
                    break
                if "time=" in line:
                    try:
                        t = line.split("time=")[1].split(" ")[0]
                        h, m, s = t.split(":")
                        sec = float(h) * 3600 + float(m) * 60 + float(s)
                        if total_seconds and total_seconds > 0:
                            pct = max(0.0, min(100.0, (sec / total_seconds) * 100.0))
                            self.ui_queue.put(("progress", pct))
                            self.ui_queue.put((
                                "status",
                                f"[{idx}/{total}] Convertendo... {pct:.1f}% ({seconds_to_hms(sec)} de {seconds_to_hms(total_seconds)})"
                            ))
                        else:
                            self.ui_queue.put(("status", f"[{idx}/{total}] Convertendo... {seconds_to_hms(sec)}"))
                    except Exception:
                        pass

            ret = self.proc.wait()

            if self.cancel_requested:
                try:
                    if out_path and os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                return False

            if ret == 0:
                self.ui_queue.put(("status", f"[{idx}/{total}] Arquivo convertido: {os.path.basename(out_path)}"))
                return True

            self.ui_queue.put(("error", f"Falha na conversao do arquivo: {os.path.basename(in_path)}"))
            return False

        except FileNotFoundError:
            self.ui_queue.put(("error", "Nao encontrei o ffmpeg/ffprobe. Instale-os e adicione ao PATH."))
            return False
        except Exception as e:
            if self.cancel_requested:
                try:
                    if out_path and os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                return False
            self.ui_queue.put(("error", f"Erro: {e}"))
            return False
        finally:
            self.proc = None

    def _convert_single_image(self, in_path, out_path, idx, total):
        try:
            if not HAS_PIL or Image is None:
                self.ui_queue.put(("error", "Conversao de imagens requer Pillow. Instale: pip install pillow"))
                return False

            self.ui_queue.put(("status", f"[{idx}/{total}] Convertendo imagem..."))
            src = _ext(in_path)
            dst = _ext(out_path)

            def _save_image(base_image):
                fmt = dst.upper()
                save_kwargs = {}
                image_to_save = base_image
                converted = None

                if dst in ("jpg", "jpeg"):
                    if base_image.mode in ("RGBA", "LA", "P"):
                        converted = base_image.convert("RGB")
                        image_to_save = converted
                    save_kwargs["quality"] = 92
                    fmt = "JPEG"
                elif dst == "webp":
                    fmt = "WEBP"
                    save_kwargs["quality"] = 92
                elif dst in ("tif", "tiff"):
                    fmt = "TIFF"
                elif dst == "bmp":
                    fmt = "BMP"

                image_to_save.save(out_path, fmt, **save_kwargs)
                if converted is not None:
                    converted.close()

            if src == "cr2":
                if not HAS_RAWPY:
                    self.ui_queue.put(("error", "Para converter CR2 instale rawpy: pip install rawpy"))
                    return False
                try:
                    import rawpy  # pyright: ignore[reportMissingImports]
                except Exception:
                    self.ui_queue.put(("error", "Falha ao carregar rawpy. Instale com: pip install rawpy"))
                    return False

                with rawpy.imread(in_path) as raw:
                    rgb = raw.postprocess()

                im = Image.fromarray(rgb)
                try:
                    _save_image(im)
                finally:
                    im.close()
            else:
                with Image.open(in_path) as im:
                    _save_image(im)

            if self.cancel_requested:
                try:
                    if out_path and os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                return False

            self.ui_queue.put(("progress", 100))
            self.ui_queue.put(("status", f"[{idx}/{total}] Arquivo convertido: {os.path.basename(out_path)}"))
            return True

        except Exception as e:
            if self.cancel_requested:
                try:
                    if out_path and os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass
                return False
            self.ui_queue.put(("error", f"Erro na conversao de imagem ({os.path.basename(in_path)}): {e}"))
            return False

    def _probe_duration(self, path):
        try:
            out = subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", path],
                text=True,
                creationflags=create_no_window_flags(),
                stderr=subprocess.DEVNULL
            )
            return out.strip()
        except Exception:
            return None

    def _drain_ui_queue(self):
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()

                if kind == "progress":
                    self.progress_var.set(payload)

                elif kind == "status":
                    self.status_var.set(payload)
                    self.on_status(payload)

                elif kind == "done":
                    info = payload if isinstance(payload, dict) else {"message": str(payload)}
                    message = info.get("message") or "Conversao concluida."
                    successes = info.get("successes", 0) or 0
                    failures = info.get("failures", 0) or 0
                    total = info.get("total")
                    if total is None:
                        total = successes + failures

                    self.is_converting = False
                    self._hide_progress()
                    self.progress_var.set(100 if total else 0)
                    self.status_var.set(message)
                    self.on_status(message)

                    self._update_action_state()
                    self._current_output_path = None

                    last_out = info.get("last_output")
                    self.ultimo_arquivo_convertido = last_out or ""
                    self.open_btn.config(state=NORMAL if last_out else DISABLED)

                    if failures:
                        messagebox.showwarning("Aviso", message)
                    else:
                        messagebox.showinfo("Sucesso", message)

                elif kind == "canceled":
                    self.is_converting = False
                    self._hide_progress()
                    self.status_var.set(payload)
                    self.on_status(payload)
                    self.progress_var.set(0)
                    self._update_action_state()
                    self.open_btn.config(state=DISABLED)
                    self._current_output_path = None

                elif kind == "error":
                    self.on_status("Erro no conversor")
                    messagebox.showerror("Erro", str(payload))

        except queue.Empty:
            pass
        finally:
            if not self.is_converting and self.cancel_btn["state"] == NORMAL:
                self._update_action_state()
            self.after(100, self._drain_ui_queue)

    def abrir_pasta(self):
        if self.ultimo_arquivo_convertido and os.path.exists(self.ultimo_arquivo_convertido):
            pasta = os.path.dirname(self.ultimo_arquivo_convertido)
            try:
                if sys.platform.startswith("win"):
                    os.startfile(pasta)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", pasta])
                else:
                    subprocess.Popen(["xdg-open", pasta])
            except Exception as e:
                messagebox.showerror("Erro", f"Nao foi possivel abrir a pasta: {e}")
        else:
            messagebox.showerror("Erro", "Nenhum arquivo convertido encontrado.")
