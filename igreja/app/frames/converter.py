# app/frames/converter.py
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
    HAS_DND, HAS_PIL, HAS_RAWPY, DND_FILES, Image,
    create_no_window_flags, ffmpeg_cmd, ffprobe_cmd, seconds_to_hms, _ext,
)

# ---------- Conversor ----------
VIDEO_EXTS = {"mp4", "avi", "mkv", "mov", "webm", "flv", "m4v"}
AUDIO_EXTS = {"wav", "mp3"}
IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff", "cr2"}
ALL_EXTS = VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS


def is_video_file(p): return _ext(p) in VIDEO_EXTS or _ext(p) in AUDIO_EXTS
def is_image_file(p): return _ext(p) in IMAGE_EXTS


class ConverterFrame(OutputFolderMixin, ttk.Frame):
    def __init__(self, master, on_status):
        super().__init__(master)
        self.on_status = on_status

        self.input_files = []
        self.ultimo_arquivo_convertido = ""
        self.formato_destino = tk.StringVar(value="mp4")
        self.output_name_var = tk.StringVar()
        self.output_name_vars = {}
        self._output_name_defaults = {}
        self.remove_audio = tk.BooleanVar(value=False)
        self.quality_preset = tk.StringVar(value="Alta qualidade")
        self.init_output_folder("Mesma pasta do arquivo original")

        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="")
        self.is_converting = False
        self.proc = None
        self.cancel_requested = False
        self._current_output_path = None
        self._last_action_key_ts = 0.0
        self.ui_queue = queue.Queue()

        self.video_formats = ["mp3", "mp4", "avi", "mkv", "mov", "gif"]
        self.image_formats = ["jpg", "png", "webp", "tiff", "bmp"]
        self.current_mode = "video"

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
        canvas_bg = self.winfo_toplevel().style.lookup("Card.TFrame", "background") or self.winfo_toplevel().style.lookup("TFrame", "background")
        self.canvas_frame = ttk.Frame(self, style="ContentHost.TFrame")
        self.canvas_frame.pack(fill="both", expand=True)
        self.scroll_canvas = tk.Canvas(self.canvas_frame, highlightthickness=0, borderwidth=0, background=canvas_bg)
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.scroll_canvas.yview)
        self.scroll_canvas.configure(yscrollcommand=None)
        self.scroll_canvas.bind("<Configure>", self._on_scroll_canvas_configure)
        self.scroll_canvas.bind("<Enter>", self._bind_mousewheel_scroll)
        self.scroll_canvas.bind("<Leave>", self._unbind_mousewheel_scroll)

        card = ttk.Frame(self.scroll_canvas, padding=20, style="Card.TFrame")
        self.card = card
        self.card_window = self.scroll_canvas.create_window((0, 0), window=self.card, anchor="nw")
        self.card.bind("<Configure>", self._on_card_configure)
        self.card.bind("<Enter>", self._bind_mousewheel_scroll)
        self.card.bind("<Leave>", self._unbind_mousewheel_scroll)

        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Conversor de Video / Audio / Imagem", style="SectionTitle.TLabel").pack(side="left")
        ttk.Separator(card).pack(fill="x", pady=12)

        # --- Arquivos ---
        files_frame = ttk.Labelframe(card, text="Arquivos", style="Hero.TLabelframe")
        files_frame.pack(fill="x")
        files_inner = ttk.Frame(files_frame, padding=12, style="SurfaceAlt.TFrame")
        files_inner.pack(fill="x")
        files_inner.columnconfigure(1, weight=1)

        ttk.Button(files_inner, text="Adicionar arquivo(s)", command=self.selecionar_arquivos, style="PrimaryAction.TButton").grid(
            row=0, column=0, sticky="w"
        )
        self.remove_btn = ttk.Button(files_inner, text="Remover", command=self.remover_arquivos, style="DangerAction.TButton")
        self.remove_btn.grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.label_video = ttk.Label(files_inner, text="Nenhum arquivo selecionado", font=("Helvetica", 12), style="SurfaceAlt.TLabel")
        self.label_video.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.label_formato = ttk.Label(files_inner, text="", font=("Helvetica", 12), style="SurfaceMuted.TLabel")
        self.label_formato.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        if HAS_DND:
            ttk.Label(
                files_inner,
                text="Arraste e solte videos/audios (mp4, mkv, mp3...) ou imagens (jpg, png, cr2...)",
                style="SurfaceMuted.TLabel",
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 4))

        # --- Configuracao de saida ---
        self.opts_frame = ttk.Labelframe(card, text="Opções")
        self.opts_frame.pack(fill="x", pady=(10, 0))
        opts_inner = ttk.Frame(self.opts_frame, padding=12, style="SurfaceAlt.TFrame")
        opts_inner.pack(fill="x")
        opts_inner.columnconfigure(1, weight=1)

        self.fmt_row = ttk.Frame(opts_inner, style="SurfaceAlt.TFrame")
        self.fmt_row_visible = False
        self.fmt_row.columnconfigure(1, weight=1)
        ttk.Label(self.fmt_row, text="Converter para:", font=("Helvetica", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.format_menu = ttk.Combobox(self.fmt_row, textvariable=self.formato_destino, values=[], state="readonly", width=14)
        self.format_menu.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.format_menu.bind("<<ComboboxSelected>>", lambda _e: self._refresh_output_name())

        self.quality_row = ttk.Frame(opts_inner, style="SurfaceAlt.TFrame")
        self.quality_row.columnconfigure(1, weight=1)
        ttk.Label(self.quality_row, text="Qualidade:", font=("Helvetica", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.quality_menu = ttk.Combobox(
            self.quality_row,
            textvariable=self.quality_preset,
            values=["Alta qualidade", "Equilibrado", "Compacto"],
            state="readonly",
            width=16,
        )
        self.quality_menu.grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.audio_row = ttk.Frame(self.opts_frame, style="SurfaceAlt.TFrame")
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
            style="SurfaceMuted.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.output_row = ttk.Frame(self.opts_frame, style="SurfaceAlt.TFrame")
        self.output_row.columnconfigure(1, weight=1)
        ttk.Label(self.output_row, text="Nome do arquivo:", font=("Helvetica", 13, "bold")).grid(row=0, column=0, sticky="w")
        self.output_name_entry = ttk.Entry(self.output_row, textvariable=self.output_name_var, width=32)
        self.output_name_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.output_name_hint = ttk.Label(self.output_row, text="Editavel quando houver 1 arquivo selecionado.", style="SurfaceMuted.TLabel")
        self.output_name_hint.grid(
            row=0, column=2, sticky="w", padx=(10, 0)
        )
        self.output_name_entry.configure(state=DISABLED)
        self.output_row.pack(fill="x", pady=(10, 0))

        self.batch_output_frame = ttk.Labelframe(self.opts_frame, text="Nomes por arquivo")
        self.batch_output_inner = ttk.Frame(self.batch_output_frame, padding=12, style="SurfaceAlt.TFrame")
        self.batch_output_inner.pack(fill="x")
        self.batch_output_inner.columnconfigure(1, weight=1)
        self.batch_output_frame.pack_forget()

        self.dest_row = ttk.Frame(self.opts_frame, style="SurfaceAlt.TFrame")
        self.dest_row.columnconfigure(1, weight=1)
        ttk.Button(self.dest_row, text="Escolher pasta de destino", command=self.choose_dest_folder, style="Action.TButton").grid(
            row=0, column=0, sticky="w"
        )
        self.dest_label = ttk.Label(
            self.dest_row,
            text=self.get_destination_label_text(),
            style="SurfaceMuted.TLabel",
        )
        self.dest_label.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.dest_row.pack(fill="x", pady=(10, 0))

        # --- Acoes ---
        self.controls_frame = ttk.Frame(card, style="Card.TFrame")
        self.controls_frame.pack(fill="x", pady=(10, 6))
        self.convert_btn = ttk.Button(self.controls_frame, text="Converter", command=self.start_conversion, style="PrimaryAction.TButton", state=DISABLED)
        self.convert_btn.pack(side="left")
        self.cancel_btn = ttk.Button(self.controls_frame, text="Cancelar", command=self.cancel_conversion, style="Action.TButton", state=DISABLED)
        self.cancel_btn.pack(side="left", padx=(10, 0))
        self.cancel_btn.pack_forget()
        self.controls_frame.pack_forget()

        self.progress_frame = ttk.Frame(card, padding=10, style="SurfaceAlt.TFrame")
        self.progress = ttk.Progressbar(self.progress_frame, orient=tk.HORIZONTAL, mode="determinate", variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x")
        self.status_label = ttk.Label(self.progress_frame, textvariable=self.status_var, font=("Helvetica", 11), style="SurfaceAlt.TLabel")
        self.status_label.pack(anchor="w", pady=(6, 0))

        # Hide the progress UI until a conversion is started.
        self._hide_progress()

        self.open_btn = ttk.Button(card, text="Abrir pasta do arquivo convertido", command=self.abrir_pasta, style="Action.TButton", state=DISABLED)
        self.open_btn.pack(pady=8)
        self.open_btn.pack_forget()
        self._update_action_state()
        self._update_visibility()
        self._update_scrollbar_visibility()

    def _on_scroll_canvas_configure(self, event):
        self.scroll_canvas.itemconfigure(self.card_window, width=event.width)
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
        self._update_scrollbar_visibility()

    def _on_card_configure(self, _event=None):
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
        self._update_scrollbar_visibility()

    def _bind_mousewheel_scroll(self, _event=None):
        if not self._is_active_screen():
            return
        self.bind_all("<MouseWheel>", self._on_outer_mousewheel, add="+")

    def _unbind_mousewheel_scroll(self, _event=None):
        try:
            self.unbind_all("<MouseWheel>")
        except Exception:
            pass

    def _on_outer_mousewheel(self, event):
        if not self._is_active_screen():
            return
        if self.scroll_canvas.yview() == (0.0, 1.0):
            return
        if getattr(event, "delta", 0):
            direction = -1 if event.delta > 0 else 1
            self.scroll_canvas.yview_scroll(direction, "units")
            return "break"

    def _scroll_to_bottom(self):
        if getattr(self, "scroll_canvas", None) and self.scrollbar.winfo_ismapped():
            self.after_idle(lambda: self.scroll_canvas.yview_moveto(1.0))

    def _has_scroll_context(self):
        return bool(self.input_files)

    def _update_scrollbar_visibility(self):
        if not getattr(self, "scroll_canvas", None):
            return
        try:
            self.update_idletasks()
        except Exception:
            pass
        bbox = self.scroll_canvas.bbox("all")
        if not bbox:
            self.scrollbar.pack_forget()
            self.scroll_canvas.configure(yscrollcommand=None)
            return
        content_height = bbox[3] - bbox[1]
        visible_height = self.scroll_canvas.winfo_height()
        needs_scroll = self._has_scroll_context() and visible_height > 1 and content_height > visible_height + 10
        if needs_scroll:
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(side="right", fill="y")
            self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        else:
            self.scrollbar.pack_forget()
            self.scroll_canvas.configure(yscrollcommand=None)

    def _show_format_row(self):
        if not self.fmt_row_visible:
            self.fmt_row.pack(fill="x", pady=(8, 5))
            self.fmt_row_visible = True
            self.quality_row.pack(fill="x", pady=(0, 5))

    def _hide_format_row(self):
        if self.fmt_row_visible:
            self.fmt_row.pack_forget()
            self.quality_row.pack_forget()
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

    def _default_output_name_for(self, in_path, target_ext=None):
        filename = os.path.splitext(os.path.basename(in_path))[0]
        target_ext = (target_ext or self.formato_destino.get() or "").strip()
        if target_ext:
            original_ext = _ext(in_path)
            if target_ext == original_ext and self._target_has_no_audio(in_path, target_ext):
                filename = f"{filename}_sem_audio"
            return f"{filename}.{target_ext}"
        return filename

    def _sync_output_name_vars(self):
        active_paths = {os.path.abspath(path) for path in self.input_files}
        for path in list(self.output_name_vars):
            abs_path = os.path.abspath(path)
            if abs_path not in active_paths:
                self.output_name_vars.pop(path, None)
                self._output_name_defaults.pop(path, None)

        for path in self.input_files:
            default_name = self._default_output_name_for(path)
            var = self.output_name_vars.get(path)
            previous_default = self._output_name_defaults.get(path)
            if var is None:
                var = tk.StringVar(value=default_name)
                self.output_name_vars[path] = var
            else:
                current_value = (var.get() or "").strip()
                if not current_value or current_value == previous_default:
                    var.set(default_name)
            self._output_name_defaults[path] = default_name

    def _rebuild_batch_output_fields(self):
        if not getattr(self, "batch_output_inner", None):
            return
        for child in self.batch_output_inner.winfo_children():
            child.destroy()

        if len(self.input_files) <= 1:
            return

        self._sync_output_name_vars()
        for row_idx, path in enumerate(self.input_files):
            ttk.Label(
                self.batch_output_inner,
                text=os.path.basename(path),
                style="SurfaceAlt.TLabel",
            ).grid(row=row_idx, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
            ttk.Entry(
                self.batch_output_inner,
                textvariable=self.output_name_vars[path],
                width=36,
            ).grid(row=row_idx, column=1, sticky="ew", pady=(0, 8))

    def _refresh_output_name(self):
        if not self.input_files:
            self.output_name_var.set("")
            self.output_name_entry.configure(state=DISABLED)
            self._sync_output_name_vars()
            self._rebuild_batch_output_fields()
            return

        if len(self.input_files) > 1:
            self.output_name_var.set("")
            self.output_name_entry.configure(state=DISABLED)
            self._sync_output_name_vars()
            self._rebuild_batch_output_fields()
            return

        in_path = self.input_files[0]
        self._sync_output_name_vars()
        self.output_name_var.set(self.output_name_vars[in_path].get())
        self.output_name_entry.configure(state=NORMAL)
        self._rebuild_batch_output_fields()

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

        output_dir = self.resolve_output_dir(in_path)

        if len(self.input_files) == 1:
            custom_name = (self.output_name_var.get() or "").strip()
            if custom_name:
                if "." not in os.path.basename(custom_name):
                    custom_name = f"{custom_name}.{out_ext}"
                return self._next_available_path(os.path.join(output_dir, custom_name))
        else:
            custom_var = self.output_name_vars.get(in_path)
            custom_name = (custom_var.get() if custom_var else "").strip()
            if custom_name:
                if "." not in os.path.basename(custom_name):
                    custom_name = f"{custom_name}.{out_ext}"
                return self._next_available_path(os.path.join(output_dir, custom_name))

        if out_ext == original_ext:
            suffix = "_sem_audio" if self._target_has_no_audio(in_path, out_ext) else "_convertido"
            filename = f"{filename}{suffix}"

        return self._next_available_path(os.path.join(output_dir, filename + f".{out_ext}"))

    def _quality_settings(self):
        preset = self.quality_preset.get() or "Alta qualidade"
        mapping = {
            "Alta qualidade": {
                "video_crf": "20",
                "video_preset": "slow",
                "audio_bitrate": "192k",
                "mp3_quality": "0",
                "image_quality": 95,
                "png_compress_level": 6,
                "gif_fps": 15,
            },
            "Equilibrado": {
                "video_crf": "24",
                "video_preset": "medium",
                "audio_bitrate": "128k",
                "mp3_quality": "2",
                "image_quality": 88,
                "png_compress_level": 8,
                "gif_fps": 12,
            },
            "Compacto": {
                "video_crf": "28",
                "video_preset": "faster",
                "audio_bitrate": "96k",
                "mp3_quality": "5",
                "image_quality": 78,
                "png_compress_level": 9,
                "gif_fps": 10,
            },
        }
        return mapping.get(preset, mapping["Alta qualidade"])

    def _is_active_screen(self):
        top = self.winfo_toplevel()
        return getattr(top, "current_screen", None) == getattr(self, "screen_key", None)

    def _handle_return_key(self, event=None):
        if not self._is_active_screen() or self.is_converting or str(self.convert_btn["state"]) != str(NORMAL):
            return
        if isinstance(event.widget, tk.Text):
            return
        now = time.monotonic()
        if now - self._last_action_key_ts < 0.35:
            return "break"
        self._last_action_key_ts = now
        self.start_conversion()
        return "break"

    def _handle_escape_key(self, _event=None):
        if not self._is_active_screen() or not self.is_converting:
            return
        self.cancel_conversion()
        return "break"

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
            self.remove_btn.grid()
            if not self.opts_frame.winfo_ismapped():
                self.opts_frame.pack(fill="x", pady=(10, 0))
            if len(self.input_files) > 1:
                self.output_row.pack_forget()
                if not self.batch_output_frame.winfo_ismapped():
                    self.batch_output_frame.pack(fill="x", pady=(10, 0))
            else:
                if not self.output_row.winfo_ismapped():
                    self.output_row.pack(fill="x", pady=(10, 0))
                self.batch_output_frame.pack_forget()
            if not self.controls_frame.winfo_ismapped():
                self.controls_frame.pack(fill="x", pady=(10, 6))
            if self.is_converting:
                if not self.cancel_btn.winfo_ismapped():
                    self.cancel_btn.pack(side="left", padx=(10, 0))
            elif self.cancel_btn.winfo_ismapped():
                self.cancel_btn.pack_forget()
            if self.ultimo_arquivo_convertido and not self.open_btn.winfo_ismapped():
                self.open_btn.pack(pady=8)
            elif not self.ultimo_arquivo_convertido and self.open_btn.winfo_ismapped():
                self.open_btn.pack_forget()
        else:
            self.remove_btn.grid_remove()
            self.opts_frame.pack_forget()
            if not self.output_row.winfo_ismapped():
                self.output_row.pack(fill="x", pady=(10, 0))
            self.batch_output_frame.pack_forget()
            self.controls_frame.pack_forget()
            self.cancel_btn.pack_forget()
            self.open_btn.pack_forget()

        # Only show progress when conversion is running.
        if self.is_converting:
            self._show_progress()
        else:
            self._hide_progress()
        if len(self.input_files) > 1:
            self.output_name_hint.configure(text="Edite abaixo o nome de saída de cada arquivo.")
        else:
            self.output_name_hint.configure(text="Editavel quando houver 1 arquivo selecionado.")
        self._update_scrollbar_visibility()
        if self.input_files:
            self._scroll_to_bottom()

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
            self._set_selected_files(list(paths), append=True)

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
            self._set_selected_files(paths, append=True)

    def _set_selected_files(self, caminhos, append=False):
        previous_files = list(self.input_files) if append else []
        merged = []
        seen = set()
        for path in [*previous_files, *list(caminhos)]:
            abs_path = os.path.abspath(path)
            low = abs_path.lower()
            if low in seen or not os.path.isfile(abs_path) or _ext(abs_path) not in ALL_EXTS:
                continue
            seen.add(low)
            merged.append(abs_path)
        self.input_files = merged

        if not self.input_files:
            self.label_video.config(text="Nenhum arquivo selecionado")
            self.label_formato.config(text="")
            self._update_format_menu()
            self._update_visibility()
            return

        all_video = all(is_video_file(p) for p in self.input_files)
        all_image = all(is_image_file(p) for p in self.input_files)
        if not (all_video or all_image):
            if append and previous_files:
                self.input_files = previous_files
                self._set_selected_files(previous_files, append=False)
            else:
                self.input_files = []
                self.label_video.config(text="Nenhum arquivo selecionado")
                self.label_formato.config(text="")
                self._update_format_menu()
                self._update_visibility()
            messagebox.showerror("Selecao invalida", "Nao misture imagens com videos/audios na mesma fila.")
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
        self.output_name_vars = {}
        self._output_name_defaults = {}
        self.output_name_entry.configure(state=DISABLED)
        self._hide_format_row()
        self._hide_audio_row()
        self.format_menu.config(values=[])
        self.quality_preset.set("Alta qualidade")
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

        try:
            self.ensure_output_dir(self.input_files[0])
        except Exception as exc:
            messagebox.showerror("Erro", f"Nao foi possivel preparar a pasta de destino:\n{exc}")
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
        else:
            for in_path in self.input_files:
                custom_var = self.output_name_vars.get(in_path)
                custom_name = (custom_var.get() if custom_var else "").strip()
                if not custom_name:
                    messagebox.showerror("Erro", f"Informe um nome de saida para {os.path.basename(in_path)}.")
                    return

        self.is_converting = True
        self.cancel_requested = False
        self._current_output_path = None

        self.convert_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.open_btn.config(state=DISABLED)
        self._show_progress()
        self._update_action_state()
        self._update_visibility()

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
            settings = self._quality_settings()
            source_is_audio = _ext(in_path) in AUDIO_EXTS

            if out_ext == "mp3":
                cmd = ffmpeg_cmd(
                    "-y", "-i", in_path, "-vn",
                    "-acodec", "libmp3lame",
                    "-q:a", settings["mp3_quality"],
                    out_path,
                )
            elif source_is_audio:
                if out_ext == "gif":
                    self.ui_queue.put(("error", f"Nao e possivel converter audio para GIF: {os.path.basename(in_path)}"))
                    return False

                audio_codec = "libopus" if out_ext == "webm" else "aac"
                if out_ext == "avi":
                    audio_codec = "libmp3lame"

                cmd = ffmpeg_cmd(
                    "-y", "-i", in_path, "-vn",
                    "-c:a", audio_codec,
                    "-b:a", settings["audio_bitrate"],
                    out_path,
                )
            elif out_ext == "gif":
                cmd = ffmpeg_cmd(
                    "-y", "-i", in_path,
                    "-vf", f"fps={settings['gif_fps']},scale=iw:-1:flags=lanczos",
                    "-loop", "0",
                    out_path,
                )
            elif remove_audio:
                cmd = ffmpeg_cmd(
                    "-y", "-i", in_path,
                    "-c:v", "libx264",
                    "-preset", settings["video_preset"],
                    "-crf", settings["video_crf"],
                    "-an",
                    "-movflags", "+faststart",
                    out_path,
                )
            else:
                if out_ext == "webm":
                    cmd = ffmpeg_cmd(
                        "-y", "-i", in_path,
                        "-c:v", "libvpx-vp9",
                        "-crf", settings["video_crf"],
                        "-b:v", "0",
                        "-c:a", "libopus",
                        "-b:a", settings["audio_bitrate"],
                        out_path,
                    )
                else:
                    extra_args = ["-movflags", "+faststart"] if out_ext in {"mp4", "mov"} else []
                    cmd = ffmpeg_cmd(
                        "-y", "-i", in_path,
                        "-c:v", "libx264",
                        "-preset", settings["video_preset"],
                        "-crf", settings["video_crf"],
                        "-c:a", "aac",
                        "-b:a", settings["audio_bitrate"],
                        *extra_args,
                        out_path,
                    )

            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
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
            self.ui_queue.put(("error", "Nao encontrei ffmpeg/ffprobe no executavel nem no PATH."))
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
                    save_kwargs["quality"] = self._quality_settings()["image_quality"]
                    fmt = "JPEG"
                elif dst == "webp":
                    fmt = "WEBP"
                    save_kwargs["quality"] = self._quality_settings()["image_quality"]
                elif dst == "png":
                    save_kwargs["compress_level"] = self._quality_settings()["png_compress_level"]
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
                ffprobe_cmd("-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", path),
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
            if self.winfo_exists():
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
