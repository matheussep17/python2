# app/frames/baixar_videos.py
import os
import re
import sys
import queue
import threading
import urllib.parse
import urllib.request
import base64
import io
import time
import tempfile
import subprocess
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk

import requests
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.utils import (
    format_bytes,
    get_available_js_runtimes,
    get_ffmpeg_bin_dir,
    get_output_folder,
    save_output_folder,
)


def app_base_dir() -> Path:
    """
    Em DEV: .../igreja
    Em EXE (PyInstaller): pasta do executável
    """
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(sys.executable))
    return Path(__file__).resolve().parents[2]  # .../igreja


class BaixarFrame(ttk.Frame):
    def __init__(self, master, on_status):
        super().__init__(master)
        self.on_status = on_status

        self.destination_folder = self.load_config()
        self.selected_format = ttk.StringVar(value="Música")
        self.selected_quality = ttk.StringVar(value="1080p")
        self.video_profile = ttk.StringVar(value="Compatível com Holyrics")

        self.downloaded_file = None
        self._reserved_output_file = None
        self.cancel_requested = False
        self._last_tmp_file = None
        self._yt_dlp = None
        self._pytubefix = None
        self._quality_pack_options = {}
        self.is_running = False
        self._last_action_key_ts = 0.0

        self._url_preview_job = None
        self._last_preview_url = None
        self._thumb_photo = None

        self._build_ui()

        self.ui_queue = queue.Queue()
        self.bind_all("<Return>", self._handle_return_key, add="+")
        self.bind_all("<Escape>", self._handle_escape_key, add="+")
        self.after(100, self._drain_ui_queue)
        self._apply_quality_visibility()

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

        self.service = ttk.StringVar(value="YouTube")
        self.header_label = ttk.Label(header, text="Downloader de midia - YouTube", style="SectionTitle.TLabel")
        self.header_label.pack(side="left")

        svc_frame = ttk.Frame(header, style="Card.TFrame")
        svc_frame.pack(side="right")
        ttk.Label(svc_frame, text="Servico:", font=("Helvetica", 12)).pack(side="left")
        self.service_menu = ttk.Combobox(
            svc_frame,
            textvariable=self.service,
            values=["YouTube", "Instagram"],
            state="readonly",
            width=12,
        )
        self.service_menu.pack(side="left", padx=(8, 0))
        self.service_menu.bind("<<ComboboxSelected>>", self._on_service_change)

        ttk.Separator(card).pack(fill="x", pady=12)

        # --- URL / Serviço ---
        url_frame = ttk.Labelframe(card, text="Origem", style="Hero.TLabelframe")
        url_frame.pack(fill="x")
        url_inner = ttk.Frame(url_frame, padding=12, style="SurfaceAlt.TFrame")
        url_inner.pack(fill="x")
        url_inner.columnconfigure(1, weight=1)

        self.url_label = ttk.Label(url_inner, text="URL:", font=("Helvetica", 13))
        self.url_label.grid(row=0, column=0, sticky="w")
        self.url_entry = ttk.Entry(url_inner, width=60, font=("Helvetica", 12))
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self._add_entry_context_menu(self.url_entry)
        self.url_entry.bind("<KeyRelease>", self._on_url_changed)
        self.url_entry.bind("<<Paste>>", lambda _e: self.after(10, self._on_url_changed))
        self.url_entry.bind("<<Cut>>", lambda _e: self.after(10, self._on_url_changed))

        self.url_status_label = ttk.Label(url_inner, text="Cole um link para começar.", style="SurfaceMuted.TLabel")
        self.url_status_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.url_title_var = tk.StringVar(value="")
        self.url_title_label = ttk.Label(url_inner, textvariable=self.url_title_var, style="SurfaceMuted.TLabel")
        self.url_title_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # Thumbnail preview (carrega ao colar URL válida)
        self.thumbnail_label = ttk.Label(url_inner)
        self.thumbnail_label.grid(row=0, column=2, rowspan=3, sticky="ne", padx=(12, 0))
        url_inner.columnconfigure(2, weight=0)

        # --- Destino ---
        dest_frame = ttk.Labelframe(card, text="Destino", style="TLabelframe")
        dest_frame.pack(fill="x", pady=(10, 0))
        dest_inner = ttk.Frame(dest_frame, padding=12, style="SurfaceAlt.TFrame")
        dest_inner.pack(fill="x")
        dest_inner.columnconfigure(1, weight=1)

        ttk.Button(dest_inner, text="Escolher pasta de destino", command=self.choose_dest_folder, style="Action.TButton").grid(
            row=0, column=0, sticky="w"
        )
        self.dest_label = ttk.Label(
            dest_inner, text=self.destination_folder or "Nenhuma pasta selecionada", anchor="w", font=("Helvetica", 12), style="SurfaceAlt.TLabel"
        )
        self.dest_label.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        # --- Opções ---
        self.opts_frame = ttk.Labelframe(card, text="Opções")
        self.opts_frame.pack_forget()
        opts_inner = ttk.Frame(self.opts_frame, padding=12, style="SurfaceAlt.TFrame")
        opts_inner.pack(fill="x")
        opts_inner.columnconfigure(1, weight=1)
        opts_inner.columnconfigure(3, weight=1)
        opts_inner.columnconfigure(5, weight=1)

        ttk.Label(opts_inner, text="Formato:", font=("Helvetica", 13)).grid(row=0, column=0, sticky="w")
        self.format_menu = ttk.Combobox(
            opts_inner, textvariable=self.selected_format, values=["Música", "Vídeo"], state="readonly", width=12
        )
        self.format_menu.grid(row=0, column=1, sticky="w", padx=(8, 20))
        self.format_menu.bind("<<ComboboxSelected>>", self._on_format_change)

        self.quality_label = ttk.Label(opts_inner, text="Qualidade do video:", font=("Helvetica", 13))
        self.quality_label.grid(row=0, column=2, sticky="w")
        self.quality_menu = ttk.Combobox(
            opts_inner,
            textvariable=self.selected_quality,
            values=["144p", "240p", "360p", "480p", "720p", "1080p", "1440p", "2160p"],
            state="readonly",
            width=12,
        )
        self.quality_menu.grid(row=0, column=3, sticky="w", padx=(8, 0))
        self._quality_widgets = [self.quality_label, self.quality_menu]
        self._quality_pack_options = {w: w.grid_info() for w in self._quality_widgets}

        self.profile_label = ttk.Label(opts_inner, text="Perfil:", font=("Helvetica", 13))
        self.profile_label.grid(row=0, column=4, sticky="w", padx=(20, 0))
        self.profile_menu = ttk.Combobox(
            opts_inner,
            textvariable=self.video_profile,
            values=["Máxima qualidade", "Compatível com Holyrics"],
            state="readonly",
            width=24,
        )
        self.profile_menu.grid(row=0, column=5, sticky="w", padx=(8, 0))
        self._profile_widgets = [self.profile_label, self.profile_menu]
        self._profile_pack_options = {w: w.grid_info() for w in self._profile_widgets}

        # --- Ações ---
        self.controls_frame = ttk.Frame(card, style="Card.TFrame")
        self.controls_frame.pack_forget()
        self.download_btn = ttk.Button(self.controls_frame, text="Baixar agora", command=self.start_download, style="PrimaryAction.TButton", state=DISABLED)
        self.download_btn.pack(side="left")
        self.cancel_btn = ttk.Button(self.controls_frame, text="Cancelar", command=self.cancel_download, style="Action.TButton", state=DISABLED)
        self.cancel_btn.pack(side="left", padx=(10, 0))
        self.cancel_btn.pack_forget()

        self.progress_frame = ttk.Frame(card, padding=10, style="SurfaceAlt.TFrame")
        self.progress = ttk.Progressbar(self.progress_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x")
        self.status = ttk.Label(self.progress_frame, text="", font=("Helvetica", 11), style="SurfaceAlt.TLabel")
        self.status.pack(anchor="w", pady=(6, 0))

        # Progress is only shown while an operation is running.
        self._hide_progress()

        self.open_folder_button = ttk.Button(
            card, text="Abrir pasta do arquivo", command=self.open_file_location, style="Action.TButton", state=DISABLED
        )
        self.open_folder_button.pack_forget()
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
        has_url = self._is_valid_url(self.url_entry.get().strip()) if getattr(self, "url_entry", None) else False
        has_destination = bool(self.destination_folder)
        return has_url and has_destination

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

    def _normalize_path(self, path_value):
        try:
            return os.path.abspath(os.path.expanduser(str(path_value))) if path_value else ""
        except Exception:
            return str(path_value)

    def _sanitize_filename(self, value):
        text = str(value or "").strip()
        text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
        text = re.sub(r"\s+", " ", text).strip(" .")
        return text or "download"

    def _next_available_path(self, folder, stem, extension):
        extension = str(extension or "").lstrip(".")
        base_name = self._sanitize_filename(stem)
        candidate = os.path.join(folder, f"{base_name}.{extension}")
        if not os.path.exists(candidate):
            return candidate

        index = 2
        while True:
            candidate = os.path.join(folder, f"{base_name} ({index}).{extension}")
            if not os.path.exists(candidate):
                return candidate
            index += 1

    def _build_outtmpl(self, title, fmt_mode, quality_choice):
        stem = self._sanitize_filename(title)
        is_video = "deo" in str(fmt_mode or "").lower()
        is_holyrics = "Holyrics" in self.video_profile.get()
        final_ext = "mp4" if is_video and is_holyrics else "mkv" if is_video else "mp3"

        if is_video and quality_choice and quality_choice != "best":
            stem = f"{stem} [{quality_choice}]"
        elif is_video and not is_holyrics:
            stem = f"{stem} [max]"

        reserved_path = self._next_available_path(self.destination_folder, stem, final_ext)
        return f"{os.path.splitext(reserved_path)[0]}.%(ext)s", reserved_path

    def _iter_ydl_attempts(self, base_opts):
        format_attempts = base_opts.pop("_format_attempts", None)
        attempts = []

        if format_attempts:
            for fmt in format_attempts:
                attempt = dict(base_opts)
                attempt["format"] = fmt
                attempts.append(attempt)
            return attempts

        return [dict(base_opts)]

    def _build_youtube_extractor_args(self):
        return {
            "youtube": {
                "player_client": ["web"],
            }
        }

    def _fetch_youtube_oembed_title(self, url: str):
        if not (getattr(self, "service", None) and self.service.get() == "YouTube"):
            return None

        try:
            encoded_url = urllib.parse.quote(url, safe="")
            response = requests.get(
                f"https://www.youtube.com/oembed?url={encoded_url}&format=json",
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            payload = response.json()
            title = str(payload.get("title", "") or "").strip()
            return title or None
        except Exception:
            return None

    def _probe_media_info(self, url):
        y = self._yt_dlp
        extractor_args = self._build_youtube_extractor_args()
        js_runtimes = get_available_js_runtimes()
        attempts = self._iter_ydl_attempts(
            {
                "quiet": True,
                "skip_download": True,
                "noplaylist": True,
                "extract_flat": False,
                "socket_timeout": 60,
                "retries": 5,
                "fragment_retries": 5,
                "skip_unavailable_fragments": True,
                "js_runtimes": js_runtimes,
                "remote_components": {"ejs:github"},
                "extractor_args": extractor_args,
                "extractor_sleep_json": {"youtube": 2},
            }
        )
        attempts.append(
            {
                "quiet": True,
                "skip_download": True,
                "noplaylist": True,
                "extract_flat": False,
                "socket_timeout": 60,
                "retries": 3,
                "fragment_retries": 3,
                "skip_unavailable_fragments": True,
            }
        )

        last_error = None
        for probe_opts in attempts:
            try:
                with y.YoutubeDL(probe_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            except Exception as exc:
                last_error = exc

        if last_error:
            raise last_error
        return {}

    def _resolve_download_target(self, url, fmt_mode, quality_choice):
        try:
            info = self._probe_media_info(url)
        except Exception:
            info = {}

        title = (
            (info or {}).get("title")
            or (info or {}).get("fulltitle")
            or (info or {}).get("track")
            or (info or {}).get("alt_title")
            or (info or {}).get("id")
            or self._sanitize_filename(self.url_title_var.get()).replace("_", " ")
            or self._fetch_youtube_oembed_title(url)
            or "download"
        )
        return self._build_outtmpl(title, fmt_mode, quality_choice)

    def load_config(self):
        try:
            return self._normalize_path(get_output_folder())
        except Exception:
            return ""

    def save_config(self):
        try:
            self.destination_folder = save_output_folder(self.destination_folder)
        except Exception as e:
            try:
                self.on_status(f"Aviso: não foi possível salvar a configuração ({e})")
            except Exception:
                pass

    def choose_dest_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.destination_folder = folder
            self.dest_label.config(text=folder)
            self.save_config()
            self._update_action_state()

    def _on_format_change(self, _evt=None):
        self._apply_quality_visibility()

    def _is_valid_url(self, url: str) -> bool:
        return bool(re.match(r"^https?://", (url or "").strip(), re.IGNORECASE))

    def _on_url_changed(self, _evt=None):
        url = (self.url_entry.get() or "").strip()
        if not url:
            self.url_status_label.config(text="Cole um link para começar.", foreground=None)
            self.url_title_var.set("")
            self.thumbnail_label.config(image="")
            self._thumb_photo = None
        elif self._is_valid_url(url):
            self.url_status_label.config(text="URL válida", foreground="#10B981")
            self._schedule_url_preview(url)
        else:
            self.url_status_label.config(text="URL inválida", foreground="#F87171")
            self.url_title_var.set("")
            self.thumbnail_label.config(image="")
            self._thumb_photo = None

        self._update_action_state()

    def _schedule_url_preview(self, url: str):
        if self._url_preview_job is not None:
            try:
                self.after_cancel(self._url_preview_job)
            except Exception:
                pass
        self._url_preview_job = self.after(500, lambda: self._trigger_url_preview(url))

    def _trigger_url_preview(self, url: str):
        self._url_preview_job = None
        if not url or url == self._last_preview_url:
            return
        self._last_preview_url = url
        self.url_title_var.set("(buscando título...)")
        threading.Thread(target=self._fetch_url_title, args=(url,), daemon=True).start()

    def _fetch_url_title(self, url: str):
        try:
            import yt_dlp

            self._yt_dlp = yt_dlp
            info = self._probe_media_info(url)

            title = (
                (info or {}).get("title")
                or (info or {}).get("fulltitle")
                or (info or {}).get("track")
                or (info or {}).get("alt_title")
                or "(sem título)"
            )
            self._queue_event("preview_title", title)

            thumb = (info or {}).get("thumbnail")
            if not thumb:
                thumbs = (info or {}).get("thumbnails") or []
                if thumbs:
                    thumbs_sorted = sorted(
                        [t for t in thumbs if isinstance(t, dict) and t.get("url")],
                        key=lambda t: t.get("width") or 0,
                        reverse=True,
                    )
                    thumb = thumbs_sorted[0].get("url") if thumbs_sorted else None

            if thumb:
                self._fetch_thumbnail(thumb)
        except Exception:
            fallback_title = self._fetch_youtube_oembed_title(url)
            self._queue_event("preview_title", fallback_title or "(não foi possível obter o título)")

    def _fetch_thumbnail(self, url: str):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = resp.read()

            try:
                from PIL import Image
            except Exception:
                Image = None

            if Image:
                try:
                    img = Image.open(io.BytesIO(data))
                    img.thumbnail((240, 135), Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    data = buf.getvalue()
                except Exception:
                    pass

            self._queue_event("preview_thumb", data)
        except Exception:
            pass

    def _is_video(self):
        return self.selected_format.get() == "Vídeo"

    def _is_youtube_service(self):
        return bool(getattr(self, "service", None) and self.service.get() == "YouTube")

    def _is_music_mode(self, fmt_mode=None):
        value = str(fmt_mode if fmt_mode is not None else self.selected_format.get() or "").lower()
        return "mús" in value or "mus" in value

    def _is_holyrics_profile(self, profile=None):
        value = str(profile if profile is not None else self.video_profile.get() or "")
        return "Holyrics" in value

    def _apply_quality_visibility(self):
        if getattr(self, "service", None) and self.service.get() == "YouTube" and self._is_video():
            for w in self._quality_widgets:
                try:
                    if not w.winfo_ismapped():
                        grid_options = self._quality_pack_options.get(w) or {}
                        w.grid(**grid_options)
                except Exception:
                    pass
            for w in self._profile_widgets:
                try:
                    if not w.winfo_ismapped():
                        grid_options = self._profile_pack_options.get(w) or {}
                        w.grid(**grid_options)
                except Exception:
                    pass
        else:
            for w in self._quality_widgets:
                try:
                    w.grid_forget()
                except Exception:
                    pass
            for w in self._profile_widgets:
                try:
                    w.grid_forget()
                except Exception:
                    pass

    def _on_service_change(self, _evt=None):
        svc = self.service.get()
        self.header_label.config(text=f"Downloader de midia - {svc}")
        try:
            self.url_label.config(text=f"{svc} URL:")
        except Exception:
            pass
        try:
            top = self.winfo_toplevel()
            top.title(f"Mídia Suite — Baixar — {svc}")
        except Exception:
            pass
        self._apply_quality_visibility()
        self._update_action_state()

    def _update_action_state(self):
        if self.is_running:
            self.download_btn.config(state=DISABLED)
            self.cancel_btn.config(state=NORMAL if not self.cancel_requested else DISABLED)
            self._update_visibility()
            return

        has_url = bool(self.url_entry.get().strip())
        has_destination = bool(self.destination_folder)
        self.download_btn.config(state=NORMAL if has_url and has_destination else DISABLED)
        self.cancel_btn.config(state=DISABLED)
        self._update_visibility()

    def _update_visibility(self):
        has_url = self._is_valid_url(self.url_entry.get().strip())
        has_destination = bool(self.destination_folder)

        if has_url and has_destination:
            if not self.opts_frame.winfo_ismapped():
                self.opts_frame.pack(fill="x", pady=(10, 0))
            if not self.controls_frame.winfo_ismapped():
                self.controls_frame.pack(fill="x", pady=(14, 8))
            if self.is_running:
                if not self.cancel_btn.winfo_ismapped():
                    self.cancel_btn.pack(side="left", padx=(10, 0))
            elif self.cancel_btn.winfo_ismapped():
                self.cancel_btn.pack_forget()
        else:
            self.opts_frame.pack_forget()
            self.controls_frame.pack_forget()
            self.cancel_btn.pack_forget()

        if self.downloaded_file and not self.is_running:
            if not self.open_folder_button.winfo_ismapped():
                self.open_folder_button.pack(pady=8)
        else:
            self.open_folder_button.pack_forget()

        if self.is_running:
            self._show_progress()
        else:
            self._hide_progress()
        self._update_scrollbar_visibility()
        if has_url and has_destination:
            self._scroll_to_bottom()

    def _show_progress(self):
        if getattr(self, "progress_frame", None) and not self.progress_frame.winfo_ismapped():
            self.progress_frame.pack(fill="x", pady=(8, 4))

    def _hide_progress(self):
        if getattr(self, "progress_frame", None) and self.progress_frame.winfo_ismapped():
            self.progress_frame.pack_forget()

    def _add_entry_context_menu(self, entry):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Cortar", command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_command(label="Copiar", command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label="Colar", command=lambda: entry.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Selecionar tudo", command=lambda: (entry.select_range(0, "end"), entry.icursor("end")))

        def _show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"

        entry.bind("<Button-3>", _show_menu)
        entry.bind("<Control-Button-1>", _show_menu)
        entry.bind("<Button-2>", _show_menu)

    def _queue_event(self, kind, payload=None):
        try:
            self.ui_queue.put_nowait((kind, payload))
        except queue.Full:
            pass

    def _is_active_screen(self):
        top = self.winfo_toplevel()
        return getattr(top, "current_screen", None) == getattr(self, "screen_key", None)

    def _handle_return_key(self, _event=None):
        if not self._is_active_screen() or self.is_running or str(self.download_btn["state"]) != str(NORMAL):
            return
        now = time.monotonic()
        if now - self._last_action_key_ts < 0.35:
            return "break"
        self._last_action_key_ts = now
        self.start_download()
        return "break"

    def _handle_escape_key(self, _event=None):
        if not self._is_active_screen() or not self.is_running:
            return
        self.cancel_download()
        return "break"

    def _set_thumbnail(self, data: bytes):
        try:
            if not data:
                return
            img = tk.PhotoImage(data=base64.b64encode(data))
            self._thumb_photo = img
            self.thumbnail_label.config(image=img)
        except Exception:
            pass

    def _drain_ui_queue(self):
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()

                if kind == "progress":
                    try:
                        self.progress["value"] = float(payload)
                    except Exception:
                        pass

                elif kind == "status":
                    self.status.config(text=str(payload or ""))

                elif kind == "notify":
                    self.on_status(str(payload or ""))

                elif kind == "downloaded_file":
                    self.downloaded_file = payload
                    self._update_visibility()

                elif kind == "reserved_output_file":
                    self._reserved_output_file = payload

                elif kind == "preview_title":
                    self.url_title_var.set(str(payload or ""))

                elif kind == "preview_thumb":
                    self._set_thumbnail(payload)

                elif kind == "done":
                    self._finish_ok()

                elif kind == "canceled":
                    self._finish_canceled()

                elif kind == "error":
                    self._finish_error(str(payload or ""))

        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._drain_ui_queue)

    def _quality_height(self, quality_choice):
        if quality_choice == "best":
            return None
        return "".join(ch for ch in str(quality_choice or "") if ch.isdigit()) or "1080"

    def _is_quality_strict(self, quality_choice):
        return bool(quality_choice and str(quality_choice).lower() != "best")

    def _build_yt_format(self, quality_choice):
        vfilter = "[vcodec^=avc1]"
        afilter = "[acodec^=mp4a]"

        if quality_choice == "best":
            return (
                f"(bv*{vfilter}[ext=mp4]/bv*{vfilter})"
                f"+(ba{afilter}[ext=m4a]/ba{afilter}/ba)"
                f"/b{vfilter}[ext=mp4]/b{vfilter}"
                f"/b[ext=mp4]/b"
            )

        h = self._quality_height(quality_choice)

        return (
            f"(bv*{vfilter}[ext=mp4][height={h}]/bv*{vfilter}[height={h}])"
            f"+(ba{afilter}[ext=m4a]/ba{afilter}/ba)"
            f"/b{vfilter}[ext=mp4][height={h}]/b{vfilter}[height={h}]"
            f"/b[ext=mp4][height={h}]/b[height={h}]"
        )

    def _build_yt_format_attempts(self, quality_choice):
        if quality_choice == "best":
            return [self._build_yt_format(quality_choice)]

        h = self._quality_height(quality_choice)
        vfilter = "[vcodec^=avc1]"

        return [
            self._build_yt_format(quality_choice),
            f"(bv*{vfilter}[height={h}]+ba/b{vfilter}[height={h}])"
            f"/b[ext=mp4][height={h}]"
            f"/b[height={h}]",
        ]

    def _build_yt_holyrics_relaxed_attempts(self, quality_choice):
        if quality_choice == "best":
            return [
                "(bv*+ba/b)",
                "(bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b)",
            ]

        h = self._quality_height(quality_choice)
        return [
            f"(bv*[ext=mp4][height={h}]/bv*[height={h}])"
            f"+(ba[ext=m4a]/ba)"
            f"/b[ext=mp4][height={h}]/b[height={h}]",
        ]

    def _build_best_quality_format(self, quality_choice):
        if quality_choice == "best":
            return "bv*+ba/b"

        h = self._quality_height(quality_choice)
        return f"(bv*[height={h}]+ba/b[height={h}])"

    def _build_best_quality_attempts(self, quality_choice):
        if quality_choice == "best":
            return [self._build_best_quality_format(quality_choice)]

        h = self._quality_height(quality_choice)
        return [
            self._build_best_quality_format(quality_choice),
            f"b[height={h}]",
        ]

    def _build_video_attempts(self, quality_choice):
        if quality_choice == "best":
            return [
                "bestvideo*+bestaudio/bestvideo+bestaudio/best",
                "bv*+ba/b",
            ]

        h = self._quality_height(quality_choice)
        return [
            f"(bestvideo*[height={h}]+bestaudio/bv*[height={h}]+ba/b[height={h}])",
            f"b[height={h}]",
        ]

    def _youtube_common_args(self, outtmpl, final_ext):
        return {
            "noprogress": True,
            "nocolor": True,
            "quiet": True,
            "progress_hooks": [self.ydl_hook],
            "outtmpl": outtmpl,
            "windowsfilenames": True,
            "noplaylist": True,
            "socket_timeout": 60,
            "retries": 5,
            "fragment_retries": 5,
            "skip_unavailable_fragments": True,
            "ffmpeg_location": get_ffmpeg_bin_dir() or None,
            "js_runtimes": get_available_js_runtimes(),
            "remote_components": {"ejs:github"},
            "extractor_args": self._build_youtube_extractor_args(),
            "extractor_sleep_json": {"youtube": 2},
            "merge_output_format": final_ext,
            "prefer_free_formats": False,
            "allow_unplayable_formats": False,
        }

    def _get_ffmpeg_executable(self):
        ffmpeg_dir = get_ffmpeg_bin_dir()
        if not ffmpeg_dir:
            return None
        binary = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
        return os.path.join(ffmpeg_dir, binary)

    def _run_ffmpeg(self, args, error_message):
        ffmpeg_exe = self._get_ffmpeg_executable()
        if not ffmpeg_exe or not os.path.exists(ffmpeg_exe):
            raise RuntimeError("FFmpeg não encontrado para finalizar o download.")

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0
        completed = subprocess.run(
            [ffmpeg_exe, *args],
            capture_output=True,
            text=True,
            creationflags=creationflags,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise RuntimeError(stderr or error_message)

    def _transcode_to_holyrics(self, source_path, target_path):
        self._queue_event("status", "Convertendo para MP4 compatível com Holyrics...")
        self._run_ffmpeg(
            [
                "-y",
                "-i", source_path,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                target_path,
            ],
            "Falha ao converter o vídeo para o padrão do Holyrics.",
        )

    def _extract_audio_to_mp3(self, source_path, target_path):
        self._queue_event("status", "Convertendo áudio para MP3...")
        self._run_ffmpeg(
            [
                "-y",
                "-i", source_path,
                "-vn",
                "-codec:a", "libmp3lame",
                "-q:a", "2",
                target_path,
            ],
            "Falha ao converter o áudio para MP3.",
        )

    def _merge_video_and_audio(self, video_path, audio_path, target_path, holyrics_mode):
        if holyrics_mode:
            self._queue_event("status", "Unindo vídeo e áudio no padrão do Holyrics...")
            args = [
                "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                "-map", "0:v:0",
                "-map", "1:a:0",
                target_path,
            ]
        else:
            self._queue_event("status", "Unindo vídeo e áudio...")
            args = [
                "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "copy",
                "-map", "0:v:0",
                "-map", "1:a:0",
                target_path,
            ]
        self._run_ffmpeg(args, "Falha ao unir vídeo e áudio.")

    def _downloaded_bytes_for_stream(self, stream):
        for attr in ("filesize", "filesize_approx"):
            try:
                value = getattr(stream, attr, None)
                if callable(value):
                    value = value()
                if value:
                    return int(value)
            except Exception:
                continue
        return 0

    def _parse_resolution_value(self, stream):
        value = str(getattr(stream, "resolution", "") or "")
        match = re.search(r"(\d+)\s*p", value, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return 0

        match = re.search(r"(\d+)", value)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return 0
        return 0

    def _parse_abr_value(self, stream):
        value = str(getattr(stream, "abr", "") or "")
        digits = "".join(ch for ch in value if ch.isdigit())
        return int(digits) if digits else 0

    def _pick_pytubefix_audio_stream(self, streams):
        audio_streams = [stream for stream in streams if getattr(stream, "includes_audio_track", False)]
        audio_streams.sort(key=lambda stream: self._parse_abr_value(stream), reverse=True)
        return audio_streams[0] if audio_streams else None

    def _video_stream_rank(self, stream):
        return (
            self._parse_resolution_value(stream),
            1 if not getattr(stream, "is_progressive", False) else 0,
            int(getattr(stream, "fps", 0) or 0),
            self._parse_abr_value(stream),
        )

    def _pick_pytubefix_video_stream(self, streams, quality_choice):
        target_height = None if quality_choice == "best" else int(self._quality_height(quality_choice) or "0")
        ranked = []
        for stream in streams:
            if not getattr(stream, "includes_video_track", False):
                continue
            height = self._parse_resolution_value(stream)
            ranked.append((height, self._video_stream_rank(stream), stream))

        if target_height:
            exact = [item for item in ranked if item[0] == target_height]
            if exact:
                exact.sort(key=lambda item: item[1], reverse=True)
                return exact[0][2]
            return None

        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return ranked[0][2] if ranked else None

    def _download_stream_with_pytubefix(self, stream, output_path, filename, label):
        self._queue_event("progress", 0)
        self._queue_event("status", f"{label}...")
        return stream.download(
            output_path=output_path,
            filename=filename,
            skip_existing=False,
            max_retries=2,
            timeout=30,
            interrupt_checker=lambda: self.cancel_requested,
        )

    def _pytubefix_progress_callback(self, stream, _chunk, bytes_remaining):
        try:
            total = self._downloaded_bytes_for_stream(stream)
            if total <= 0:
                return
            downloaded = max(0, total - int(bytes_remaining or 0))
            pct = max(0.0, min(100.0, (downloaded / total) * 100.0))
            self._queue_event("progress", pct)
            self._queue_event(
                "status",
                f"Baixando... {pct:.1f}% ({format_bytes(downloaded)} de {format_bytes(total)})",
            )
        except Exception:
            pass

    def _pytubefix_complete_callback(self, _stream, _filepath):
        self._queue_event("progress", 100)

    def _download_with_pytubefix(self, url, fmt_mode, quality_choice, reserved_path):
        pytubefix = self._pytubefix
        if pytubefix is None:
            raise RuntimeError("pytubefix não está disponível para fallback.")

        self._queue_event("status", "Preparando streams do YouTube...")
        clients = ("ANDROID_VR", "ANDROID", "MWEB", "WEB")
        selected_streams = None
        selected_client = None
        last_error = None

        for client_name in clients:
            try:
                self._queue_event("status", f"Consultando streams do YouTube ({client_name})...")
                yt = pytubefix.YouTube(
                    url,
                    client=client_name,
                    on_progress_callback=self._pytubefix_progress_callback,
                    on_complete_callback=self._pytubefix_complete_callback,
                )
                streams = list(yt.streams)

                if self._is_music_mode(fmt_mode):
                    audio_stream = self._pick_pytubefix_audio_stream(streams)
                    if audio_stream:
                        selected_streams = (streams, None, audio_stream)
                        selected_client = client_name
                        break
                    continue

                video_stream = self._pick_pytubefix_video_stream(streams, quality_choice)
                if not video_stream:
                    continue
                audio_stream = None if getattr(video_stream, "is_progressive", False) else self._pick_pytubefix_audio_stream(streams)
                selected_streams = (streams, video_stream, audio_stream)
                selected_client = client_name

                break
            except Exception as exc:
                last_error = exc

        if not selected_streams:
            if not self._is_music_mode(fmt_mode) and self._is_quality_strict(quality_choice):
                raise RuntimeError(f"A qualidade selecionada ({quality_choice}) não está disponível para este vídeo.")
            if last_error:
                raise last_error
            raise RuntimeError("O pytubefix não encontrou streams compatíveis para este vídeo.")

        self._queue_event("status", f"Streams carregadas. Cliente selecionado: {selected_client}.")
        streams, video_stream, audio_stream = selected_streams

        if self._is_music_mode(fmt_mode):
            if not audio_stream:
                raise RuntimeError("O fallback não encontrou faixa de áudio para este vídeo.")

            temp_dir = tempfile.mkdtemp(prefix="igreja-pytubefix-")
            temp_path = None
            try:
                downloaded = self._download_stream_with_pytubefix(
                    audio_stream,
                    temp_dir,
                    f"audio_temp.{getattr(audio_stream, 'subtype', 'mp4')}",
                    "Baixando áudio",
                )
                temp_path = downloaded or self._resolve_completed_output_path(
                    os.path.join(temp_dir, "audio_temp.mp4")
                )
                self._extract_audio_to_mp3(temp_path, reserved_path)
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                try:
                    os.rmdir(temp_dir)
                except Exception:
                    pass

            return reserved_path

        holyrics_mode = self._is_holyrics_profile()
        if not video_stream:
            if self._is_quality_strict(quality_choice):
                raise RuntimeError(f"A qualidade selecionada ({quality_choice}) não está disponível para este vídeo.")
            raise RuntimeError("O fallback não encontrou stream de vídeo compatível.")

        if getattr(video_stream, "is_progressive", False):
            temp_dir = tempfile.mkdtemp(prefix="igreja-pytubefix-")
            temp_video = None
            try:
                download_name = f"video_temp.{getattr(video_stream, 'subtype', 'mp4')}"
                downloaded = self._download_stream_with_pytubefix(
                    video_stream,
                    temp_dir,
                    download_name,
                    "Baixando vídeo",
                )
                temp_video = downloaded or self._resolve_completed_output_path(os.path.join(temp_dir, download_name))
                if holyrics_mode:
                    self._transcode_to_holyrics(temp_video, reserved_path)
                    return reserved_path

                final_ext = getattr(video_stream, "subtype", "mp4") or "mp4"
                final_path = f"{os.path.splitext(reserved_path)[0]}.{final_ext}"
                if os.path.abspath(temp_video) != os.path.abspath(final_path):
                    os.replace(temp_video, final_path)
                    temp_video = None
                return final_path
            finally:
                if temp_video and os.path.exists(temp_video):
                    try:
                        os.remove(temp_video)
                    except Exception:
                        pass
                try:
                    os.rmdir(temp_dir)
                except Exception:
                    pass

        if not audio_stream:
            raise RuntimeError("O fallback encontrou vídeo, mas não encontrou áudio compatível.")

        temp_dir = tempfile.mkdtemp(prefix="igreja-pytubefix-")
        temp_video = None
        temp_audio = None
        try:
            video_name = f"video_only.{getattr(video_stream, 'subtype', 'mp4')}"
            audio_name = f"audio_only.{getattr(audio_stream, 'subtype', 'mp4')}"
            temp_video = self._download_stream_with_pytubefix(
                video_stream,
                temp_dir,
                video_name,
                "Baixando vídeo",
            ) or self._resolve_completed_output_path(os.path.join(temp_dir, video_name))
            temp_audio = self._download_stream_with_pytubefix(
                audio_stream,
                temp_dir,
                audio_name,
                "Baixando áudio",
            ) or self._resolve_completed_output_path(os.path.join(temp_dir, audio_name))

            if holyrics_mode:
                self._merge_video_and_audio(temp_video, temp_audio, reserved_path, holyrics_mode=True)
                return reserved_path

            self._merge_video_and_audio(temp_video, temp_audio, reserved_path, holyrics_mode=False)
            return reserved_path
        finally:
            for path in (temp_video, temp_audio):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass

    def _resolve_completed_output_path(self, reserved_path, expected_ext=None):
        if reserved_path and os.path.exists(reserved_path):
            return reserved_path

        stem = os.path.splitext(reserved_path or "")[0]
        folder = os.path.dirname(reserved_path or "") or self.destination_folder
        base_name = os.path.basename(stem)

        try:
            entries = os.listdir(folder)
        except Exception:
            entries = []

        candidates = []
        for entry in entries:
            full_path = os.path.join(folder, entry)
            if not os.path.isfile(full_path):
                continue
            if os.path.splitext(entry)[0] != base_name:
                continue
            if entry.endswith((".part", ".ytdl")):
                continue
            candidates.append(full_path)

        if expected_ext:
            normalized_ext = f".{str(expected_ext).lstrip('.').lower()}"
            for candidate in candidates:
                if os.path.splitext(candidate)[1].lower() == normalized_ext:
                    return candidate

        return candidates[0] if candidates else reserved_path

    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            svc = getattr(self, "service", None) and self.service.get() or "YouTube"
            messagebox.showerror("Erro", f"Insira a URL do {svc}.")
            return
        if not self.destination_folder:
            messagebox.showerror("Erro", "Escolha a pasta de destino.")
            return

        dest = self._normalize_path(self.destination_folder)

        try:
            os.makedirs(dest, exist_ok=True)
        except PermissionError as e:
            fallback = str(app_base_dir())
            try:
                os.makedirs(fallback, exist_ok=True)
                self.destination_folder = fallback
                self.dest_label.config(text=self.destination_folder)
                self.save_config()
                messagebox.showwarning("Permissão", f"Não foi possível criar a pasta selecionada. Usando: {self.destination_folder}")
                dest = fallback
            except Exception:
                messagebox.showerror("Permissão", f"Não é possível criar a pasta: {self.destination_folder}\n{e}")
                return
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao preparar a pasta de destino: {e}")
            return

        self.destination_folder = dest

        try:
            import yt_dlp
            self._yt_dlp = yt_dlp
        except Exception:
            self._yt_dlp = None

        try:
            import pytubefix
            self._pytubefix = pytubefix
        except Exception:
            self._pytubefix = None

        if not self._yt_dlp and not (self._is_youtube_service() and self._pytubefix):
            messagebox.showerror("Dependências", "Instale: pip install yt-dlp pytubefix")
            return

        self.progress["value"] = 0
        self.status.config(text="Preparando...")
        self.open_folder_button.config(state=DISABLED)

        self.downloaded_file = None
        self._reserved_output_file = None
        self.cancel_requested = False
        self._last_tmp_file = None

        self.is_running = True
        self._show_progress()
        self._update_action_state()
        self.on_status("Download iniciado…")

        fmt_mode = self.selected_format.get()
        qual = self.selected_quality.get()
        if str(qual).lower() == "best":
            qual = "1080p"
            self.selected_quality.set(qual)

        threading.Thread(target=self.download_media_v2, args=(url, fmt_mode, qual), daemon=True).start()

    def cancel_download(self):
        if self.cancel_requested:
            return
        self.cancel_requested = True
        self.cancel_btn.config(state=DISABLED)
        self.status.config(text="Cancelando...")
        self.on_status("Cancelando download…")

    def _cleanup_partial(self):
        paths = set()
        if self._last_tmp_file:
            paths.add(self._last_tmp_file)
            if not self._last_tmp_file.endswith(".part"):
                paths.add(self._last_tmp_file + ".part")
            paths.add(self._last_tmp_file + ".ytdl")

        for p in list(paths):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    def download_media(self, url, fmt_mode, quality_choice):
        try:
            outtmpl, reserved_path = self._resolve_download_target(url, fmt_mode, quality_choice)
            self._queue_event("reserved_output_file", reserved_path)

            ensure_aac_pp = {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
            extractor_args = self._build_youtube_extractor_args()
            js_runtimes = get_available_js_runtimes()

            common_args = {
                "noprogress": True,
                "nocolor": True,
                "quiet": True,
                "progress_hooks": [self.ydl_hook],
                "outtmpl": outtmpl,
                "merge_output_format": "mp4",
                "prefer_free_formats": False,
                "allow_unplayable_formats": False,
                "windowsfilenames": True,
                "ffmpeg_location": get_ffmpeg_bin_dir() or None,
                "socket_timeout": 60,
                "retries": 5,
                "fragment_retries": 5,
                "skip_unavailable_fragments": True,
                "js_runtimes": js_runtimes,
                "extractor_args": extractor_args,
                "extractor_sleep_json": {"youtube": 2},
            }

            if fmt_mode == "Música":
                ydl_opts = {
                    **common_args,
                    "format": "bestaudio/best",
                    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
                }
            else:
                holyrics_mode = self.video_profile.get() == "Compatível com Holyrics"
                if holyrics_mode:
                    format_attempts = self._build_yt_holyrics_relaxed_attempts(quality_choice)
                else:
                    format_attempts = self._build_best_quality_attempts(quality_choice)

                ydl_opts = {
                    **common_args,
                    "format": format_attempts[0],
                    "_format_attempts": format_attempts,
                    "postprocessors": [
                        ensure_aac_pp,
                        {
                            "key": "FFmpegMetadata",
                        },
                    ],
                    "postprocessor_args": (
                        [
                            "-c:v", "libx264",
                            "-preset", "medium",
                            "-crf", "23",
                            "-c:a", "aac",
                            "-b:a", "192k",
                            "-movflags", "+faststart",
                        ]
                        if holyrics_mode
                        else [
                            "-c:v", "copy",
                            "-c:a", "copy",
                            "-movflags", "+faststart",
                        ]
                    ),
                }

                if "Holyrics" not in self.video_profile.get():
                    format_attempts = self._build_best_quality_attempts(quality_choice)
                    ydl_opts = {
                        **common_args,
                        "format": format_attempts[0],
                        "_format_attempts": format_attempts,
                        "merge_output_format": "mkv",
                    }

            y = self._yt_dlp
            last_error = None
            for attempt_opts in self._iter_ydl_attempts(ydl_opts):
                try:
                    with y.YoutubeDL(attempt_opts) as ydl:
                        ydl.download([url])
                    last_error = None
                    break
                except y.utils.DownloadCancelled:
                    self._cleanup_partial()
                    self._queue_event("canceled")
                    return
                except Exception as exc:
                    last_error = exc
                    continue

            if last_error is not None:
                raise last_error

            self._queue_event("done")

        except Exception as e:
            error_msg = str(e).lower()

            if "no supported javascript runtime" in error_msg or "js_runtimes" in error_msg:
                msg = (
                    "Node.js não encontrado. Instale Node.js (https://nodejs.org) "
                    "e adicione ao PATH do sistema."
                )
            elif "signature solving failed" in error_msg or "n challenge solving failed" in error_msg:
                msg = (
                    "O yt-dlp não conseguiu resolver a proteção atual do YouTube. "
                    "Feche e abra o app novamente. Se persistir, atualize o yt-dlp "
                    "e confirme que o Node.js está instalado e acessível."
                )
            elif "only images are available" in error_msg:
                msg = (
                    "O YouTube foi lido de forma incompleta e só miniaturas ficaram disponíveis. "
                    "Isso normalmente acontece quando o runtime JavaScript do yt-dlp falha. "
                    "Tente novamente após reiniciar o app."
                )
            elif "http error 429" in error_msg or "too many requests" in error_msg:
                msg = (
                    "YouTube limitou as requisições. Aguarde alguns minutos "
                    "antes de tentar novamente."
                )
            elif "sign in to confirm" in error_msg or "authentication" in error_msg:
                msg = (
                    "YouTube pediu verificação. Tente novamente ou use um video público. "
                    "Se o erro persistir, aguarde alguns minutos."
                )
            else:
                msg = str(e)

            if self.cancel_requested:
                self._cleanup_partial()
                self._queue_event("canceled")
                return
            self._queue_event("error", msg)

    def download_media_v2(self, url, fmt_mode, quality_choice):
        try:
            outtmpl, reserved_path = self._resolve_download_target(url, fmt_mode, quality_choice)
            self._queue_event("reserved_output_file", reserved_path)

            if self._is_music_mode(fmt_mode):
                attempt_opts_list = [{
                    **self._youtube_common_args(outtmpl, "mp3"),
                    "format": "bestaudio[ext=m4a]/bestaudio/best",
                    "keepvideo": False,
                    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
                }]
                final_path = reserved_path
            else:
                holyrics_mode = self._is_holyrics_profile()
                if holyrics_mode:
                    format_attempts = self._build_yt_holyrics_relaxed_attempts(quality_choice)
                else:
                    format_attempts = self._build_best_quality_attempts(quality_choice)

                source_outtmpl = outtmpl
                final_path = reserved_path

                if holyrics_mode:
                    source_outtmpl = f"{os.path.splitext(reserved_path)[0]}.__source__.%(ext)s"

                base_video_opts = self._youtube_common_args(
                    source_outtmpl,
                    "mp4" if holyrics_mode else "mkv",
                )
                attempt_opts_list = self._iter_ydl_attempts({
                    **base_video_opts,
                    "format": format_attempts[0],
                    "_format_attempts": format_attempts,
                })

            yt_dlp_error = None
            used_yt_dlp = False

            if self._yt_dlp is not None:
                y = self._yt_dlp
                last_error = None
                for attempt_opts in attempt_opts_list:
                    try:
                        with y.YoutubeDL(attempt_opts) as ydl:
                            ydl.download([url])
                        last_error = None
                        used_yt_dlp = True
                        break
                    except y.utils.DownloadCancelled:
                        self._cleanup_partial()
                        self._queue_event("canceled")
                        return
                    except Exception as exc:
                        last_error = exc

                if last_error is not None:
                    yt_dlp_error = last_error
            else:
                yt_dlp_error = RuntimeError("yt-dlp não está disponível.")

            used_pytubefix = False
            pytubefix_error = None

            if not used_yt_dlp and self._is_youtube_service() and self._pytubefix is not None:
                try:
                    final_path = self._download_with_pytubefix(url, fmt_mode, quality_choice, reserved_path)
                    used_pytubefix = True
                except Exception as exc:
                    pytubefix_error = exc

            if not used_yt_dlp and not used_pytubefix:
                if yt_dlp_error is not None and "requested format is not available" in str(yt_dlp_error).lower():
                    raise RuntimeError(f"A qualidade selecionada ({quality_choice}) não está disponível para este vídeo.")

                if pytubefix_error is not None and self._is_youtube_service():
                    raise RuntimeError(
                        f"Falha no yt-dlp: {yt_dlp_error}\nFalha no pytubefix: {pytubefix_error}"
                    )

                raise yt_dlp_error or pytubefix_error or RuntimeError("Falha ao baixar mídia.")

            if used_yt_dlp and not self._is_music_mode(fmt_mode) and self._is_holyrics_profile():
                source_final_path = None
                stem = os.path.splitext(reserved_path)[0]
                for ext in ("mp4", "mkv", "webm"):
                    candidate = f"{stem}.__source__.{ext}"
                    if os.path.exists(candidate):
                        source_final_path = candidate
                        break
                if not source_final_path:
                    raise RuntimeError("O vídeo foi baixado, mas o arquivo intermediário para conversão não foi encontrado.")

                self._transcode_to_holyrics(source_final_path, reserved_path)
                try:
                    if os.path.exists(source_final_path):
                        os.remove(source_final_path)
                except Exception:
                    pass

                final_path = reserved_path
            elif used_yt_dlp:
                expected_ext = "mp3" if self._is_music_mode(fmt_mode) else "mkv"
                final_path = self._resolve_completed_output_path(reserved_path, expected_ext=expected_ext)

            self.downloaded_file = final_path
            self._queue_event("downloaded_file", final_path)
            self._queue_event("done")
        except Exception as e:
            error_msg = str(e).lower()
            if "no supported javascript runtime" in error_msg or "js_runtimes" in error_msg:
                msg = (
                    "Node.js não encontrado. Instale Node.js (https://nodejs.org) "
                    "e adicione ao PATH do sistema."
                )
            elif "signature solving failed" in error_msg or "n challenge solving failed" in error_msg:
                msg = (
                    "O yt-dlp não conseguiu resolver a proteção atual do YouTube. "
                    "Atualize o yt-dlp e tente novamente."
                )
            elif "only images are available" in error_msg:
                msg = (
                    "O YouTube retornou apenas miniaturas para este vídeo. "
                    "Atualize o yt-dlp e tente novamente."
                )
            elif "requested format is not available" in error_msg:
                msg = (
                    f"A qualidade selecionada ({quality_choice}) não está disponível para este vídeo."
                )
            else:
                msg = str(e)

            self.downloaded_file = None
            if self.cancel_requested:
                self._cleanup_partial()
                self._queue_event("canceled")
                return
            self._queue_event("error", msg)

    def ydl_hook(self, d):
        if self.cancel_requested:
            raise self._yt_dlp.utils.DownloadCancelled()

        st = d.get("status")
        self._last_tmp_file = d.get("tmpfilename") or d.get("filename") or self._last_tmp_file

        if st == "finished":
            info = d.get("info_dict", {}) or {}
            fmt_note = info.get("format", "") or info.get("format_note", "") or ""
            height = info.get("height")
            chosen = f"{height}p" if height else ""
            suffix = f" - Selecionado: {chosen} {fmt_note}".strip()
            text = f"Concluído! {suffix}".strip()

            self._queue_event("progress", 100)
            self._queue_event("status", text)
            self._queue_event("notify", "Download finalizado")
            return

        if st == "downloading":
            downloaded = d.get("downloaded_bytes")
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            speed = d.get("speed")

            pct = None
            if downloaded is not None and total:
                try:
                    pct = max(0.0, min(100.0, (downloaded / total) * 100.0))
                except Exception:
                    pct = None

            if pct is not None:
                self._queue_event("progress", pct)

            parts = ["Baixando..."]
            if pct is not None:
                parts.append(f"{pct:.1f}%")

            if downloaded is not None:
                parts.append(f"({format_bytes(downloaded)} de {format_bytes(total) if total else '??'})")

            if speed:
                sp = format_bytes(speed)
                if sp:
                    parts.append(f"{sp}/s")

            msg = " - ".join([p for p in parts if p])
            self._queue_event("status", msg)
            self._queue_event("notify", msg)

    def open_file_location(self):
        try:
            path = self.downloaded_file

            folder = None
            file_path = None
            if self.destination_folder:
                folder = os.path.abspath(self.destination_folder)
                if path:
                    if os.path.isabs(path):
                        file_path = os.path.abspath(path)
                    else:
                        file_path = os.path.join(folder, os.path.basename(path))
                else:
                    file_path = None
            else:
                if not path:
                    return
                file_path = os.path.abspath(path)
                folder = os.path.dirname(file_path)

            if not folder or not os.path.exists(folder):
                return

            if sys.platform == "win32":
                try:
                    if file_path and os.path.exists(file_path):
                        subprocess.run(["explorer", "/select,", file_path])
                        return
                    else:
                        os.startfile(folder)
                        return
                except Exception:
                    try:
                        os.startfile(folder)
                    except Exception:
                        pass
                    return

            try:
                if sys.platform == "darwin":
                    subprocess.run(["open", folder])
                else:
                    subprocess.run(["xdg-open", folder])
            except Exception:
                pass
        except Exception:
            pass

    def _finish_ok(self):
        self.is_running = False
        self._hide_progress()
        self.status.config(text=self.status.cget("text") or "Download concluído!")
        self.open_folder_button.config(state=NORMAL)
        self.download_btn.config(state=NORMAL, text="Baixar agora")
        self.cancel_btn.config(state=DISABLED)
        self._update_visibility()

    def _finish_canceled(self):
        self.is_running = False
        self._hide_progress()
        self.status.config(text="Download cancelado.")
        self.progress["value"] = 0
        self.downloaded_file = None
        self._reserved_output_file = None
        self.open_folder_button.config(state=DISABLED)
        self.download_btn.config(state=NORMAL, text="Baixar agora")
        self.cancel_btn.config(state=DISABLED)
        self._update_visibility()
        self.on_status("Download cancelado")

    def _legacy_finish_error(self, msg):
        self.status.config(text=msg or "Erro no download.")
        self.download_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)
        self.open_folder_button.config(state=DISABLED)
        self.on_status(f"Erro: {msg or 'falha no download'}")

    def _legacy_finish_ok(self):
        self.is_running = False
        self.status.config(text=self.status.cget("text") or "Download concluido!")
        self.open_folder_button.config(state=NORMAL)
        self._update_action_state()

    def _legacy_finish_canceled(self):
        self.is_running = False
        self.status.config(text="Download cancelado.")
        self.progress["value"] = 0
        self.open_folder_button.config(state=DISABLED)
        self._update_action_state()
        self.on_status("Download cancelado")

    def _finish_error(self, msg):
        self.is_running = False
        self._hide_progress()
        self.status.config(text=msg or "Erro no download.")
        self.downloaded_file = None
        self._reserved_output_file = None
        self.open_folder_button.config(state=DISABLED)
        self._update_action_state()
        self._update_visibility()
        self.on_status(f"Erro: {msg or 'falha no download'}")
