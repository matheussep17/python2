# app/frames/baixar_videos.py
import os
import sys
import json
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.utils import format_bytes


def app_base_dir() -> Path:
    """
    Em DEV: .../igreja
    Em EXE (PyInstaller): pasta do executável
    """
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(sys.executable))
    return Path(__file__).resolve().parents[2]  # .../igreja


CONFIG_FILE = app_base_dir() / "config.json"


class BaixarFrame(ttk.Frame):
    def __init__(self, master, on_status):
        super().__init__(master)
        self.on_status = on_status

        self.destination_folder = self.load_config()
        self.selected_format = ttk.StringVar(value="Música")
        self.selected_quality = ttk.StringVar(value="best")

        self.downloaded_file = None
        self.cancel_requested = False
        self._last_tmp_file = None
        self._yt_dlp = None
        self._quality_pack_options = {}

        self._build_ui()

        self.ui_queue = queue.Queue()
        self.after(100, self._drain_ui_queue)
        self._apply_quality_visibility()

    def _build_ui(self):
        card = ttk.Frame(self, padding=18, bootstyle="dark")
        card.pack(fill="both", expand=True)

        header = ttk.Frame(card)
        header.pack(fill="x")

        self.service = ttk.StringVar(value="YouTube")
        self.header_label = ttk.Label(header, text="Downloader de mídia - YouTube", font=("Helvetica", 18, "bold"))
        self.header_label.pack(side="left")

        svc_frame = ttk.Frame(header)
        svc_frame.pack(side="right")
        ttk.Label(svc_frame, text="Serviço:", font=("Helvetica", 12)).pack(side="left")
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

        urlrow = ttk.Frame(card)
        urlrow.pack(fill="x")
        self.url_label = ttk.Label(urlrow, text="YouTube URL:", font=("Helvetica", 13))
        self.url_label.pack(side="left")
        self.url_entry = ttk.Entry(urlrow, width=60, font=("Helvetica", 12))
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self._add_entry_context_menu(self.url_entry)

        dest = ttk.Frame(card)
        dest.pack(fill="x", pady=(10, 0))
        ttk.Button(dest, text="Escolher pasta de destino", command=self.choose_dest_folder, bootstyle=SUCCESS).pack(
            side="left"
        )
        self.dest_label = ttk.Label(
            dest, text=self.destination_folder or "Nenhuma pasta selecionada", anchor="w", font=("Helvetica", 12)
        )
        self.dest_label.pack(side="left", fill="x", expand=True, padx=(10, 0))

        opts = ttk.Frame(card)
        opts.pack(fill="x", pady=(10, 0))
        ttk.Label(opts, text="Formato:", font=("Helvetica", 13)).pack(side="left")
        self.format_menu = ttk.Combobox(
            opts, textvariable=self.selected_format, values=["Música", "Vídeo"], state="readonly", width=12
        )
        self.format_menu.pack(side="left", padx=(8, 20))
        self.format_menu.bind("<<ComboboxSelected>>", self._on_format_change)

        self.quality_label = ttk.Label(opts, text="Qualidade do vídeo:", font=("Helvetica", 13))
        self.quality_label.pack(side="left")
        self.quality_menu = ttk.Combobox(
            opts,
            textvariable=self.selected_quality,
            values=["best", "144p", "240p", "360p", "480p", "720p", "1080p", "1440p", "2160p"],
            state="readonly",
            width=12,
        )
        self.quality_menu.pack(side="left", padx=(8, 0))
        self._quality_widgets = [self.quality_label, self.quality_menu]
        self._quality_pack_options = {w: w.pack_info() for w in self._quality_widgets}

        ctl = ttk.Frame(card)
        ctl.pack(fill="x", pady=(14, 8))
        self.download_btn = ttk.Button(ctl, text="Baixar agora", command=self.start_download, bootstyle=PRIMARY)
        self.download_btn.pack(side="left")
        self.cancel_btn = ttk.Button(ctl, text="Cancelar", command=self.cancel_download, bootstyle=SECONDARY, state=DISABLED)
        self.cancel_btn.pack(side="left", padx=(10, 0))

        prog = ttk.Frame(card, padding=10, bootstyle="secondary")
        prog.pack(fill="x", pady=(8, 4))
        self.progress = ttk.Progressbar(prog, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x")
        self.status = ttk.Label(prog, text="", font=("Helvetica", 11))
        self.status.pack(anchor="w", pady=(6, 0))

        self.open_folder_button = ttk.Button(
            card, text="Abrir pasta do arquivo", command=self.open_file_location, bootstyle=INFO, state=DISABLED
        )
        self.open_folder_button.pack(pady=8)

    def _normalize_path(self, path_value):
        try:
            return os.path.abspath(os.path.expanduser(str(path_value))) if path_value else ""
        except Exception:
            return str(path_value)

    def load_config(self):
        if CONFIG_FILE.exists():
            try:
                with CONFIG_FILE.open("r", encoding="utf-8") as f:
                    val = json.load(f).get("destination_folder", "")
                    return self._normalize_path(val)
            except Exception:
                return ""
        return ""

    def save_config(self):
        try:
            with CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump({"destination_folder": self.destination_folder}, f, ensure_ascii=False, indent=2)
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

    def _on_format_change(self, _evt=None):
        self._apply_quality_visibility()

    def _is_video(self):
        return self.selected_format.get() == "Vídeo"

    def _apply_quality_visibility(self):
        if getattr(self, "service", None) and self.service.get() == "YouTube" and self._is_video():
            for w in self._quality_widgets:
                try:
                    if not w.winfo_ismapped():
                        w.pack(**self._quality_pack_options.get(w, {}))
                except Exception:
                    pass
        else:
            for w in self._quality_widgets:
                try:
                    w.pack_forget()
                except Exception:
                    pass

    def _on_service_change(self, _evt=None):
        svc = self.service.get()
        self.header_label.config(text=f"Downloader de mídia - {svc}")
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

                elif kind == "done":
                    self._finish_ok()

                elif kind == "canceled":
                    self._finish_canceled()

                elif kind == "error":
                    self._finish_error(str(payload or ""))

        except queue.Empty:
            pass
        finally:
            self.after(100, self._drain_ui_queue)

    # --------- seleção de qualidade (EXATO e depois <= alvo) ---------
    def _build_yt_format(self, quality_choice):
        """
        Garante MP4 com H.264 (avc1) + áudio AAC (mp4a), com fallback seguro.
        Mantém sua lógica:
          1) tenta altura EXATA,
          2) depois altura <= alvo,
          3) junta com melhor áudio,
          4) fallback final.
        """
        # filtros de codec para Holyrics: H.264 + AAC
        vfilter = "[vcodec^=avc1]"
        afilter = "[acodec^=mp4a]"

        if quality_choice == "best":
            # Prioriza H.264 MP4 + AAC (m4a). Se não der, cai pra melhor vídeo H.264 e depois qualquer áudio.
            return (
                f"(bv*{vfilter}[ext=mp4]/bv*{vfilter})"
                f"+(ba{afilter}[ext=m4a]/ba{afilter}/ba)"
                f"/b{vfilter}[ext=mp4]/b{vfilter}"
                f"/b[ext=mp4]/b"
            )

        h = "".join(ch for ch in quality_choice if ch.isdigit()) or "1080"

        # EXATO -> <= alvo, sempre forçando avc1 no vídeo; áudio tenta AAC primeiro.
        fmt = (
            f"((bv*{vfilter}[ext=mp4][height={h}]/bv*{vfilter}[height={h}])"
            f"/(bv*{vfilter}[ext=mp4][height<={h}]/bv*{vfilter}[height<={h}]))"
            f"+(ba{afilter}[ext=m4a]/ba{afilter}/ba)"
            f"/b{vfilter}[ext=mp4]/b{vfilter}"
            f"/b[ext=mp4]/b"
        )
        return fmt

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
            messagebox.showerror("Dependências", "Instale: pip install yt-dlp")
            return

        self.progress["value"] = 0
        self.status.config(text="Preparando...")
        self.open_folder_button.config(state=DISABLED)

        self.downloaded_file = None
        self.cancel_requested = False
        self._last_tmp_file = None

        self.download_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.on_status("Download iniciado…")

        fmt_mode = self.selected_format.get()
        qual = self.selected_quality.get()

        threading.Thread(target=self.download_media, args=(url, fmt_mode, qual), daemon=True).start()

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
            # Pós-processo para GARANTIR AAC no resultado final (sem mudar sua lógica de fluxo)
            # Se já vier AAC, o ffmpeg costuma "copiar" rápido quando possível.
            ensure_aac_pp = {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }

            common_args = {
                "noprogress": True,
                "nocolor": True,
                "quiet": True,
                "progress_hooks": [self.ydl_hook],
                "outtmpl": os.path.join(self.destination_folder, "%(title)s.%(ext)s"),
                "merge_output_format": "mp4",
                "prefer_free_formats": False,
                "allow_unplayable_formats": False,
            }

            if fmt_mode == "Música":
                ydl_opts = {
                    **common_args,
                    "format": "bestaudio/best",
                    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
                }
            else:
                fmt = self._build_yt_format(quality_choice)

                # Além de selecionar H.264/AAC, garante que o final seja MP4 "normalizado"
                # (útil quando o áudio vem Opus e precisa virar AAC).
                ydl_opts = {
                    **common_args,
                    "format": fmt,
                    "postprocessors": [
                        ensure_aac_pp,
                        # recodifica/normaliza áudio para AAC se necessário
                        {
                            "key": "FFmpegMetadata",
                        },
                    ],
                    # Força recode apenas quando necessário: usa ffmpeg e parâmetros seguros.
                    "postprocessor_args": [
                        "-c:v", "copy",        # mantém H.264 selecionado (rápido)
                        "-c:a", "aac",         # garante AAC (Holyrics)
                        "-b:a", "192k",
                        "-movflags", "+faststart",
                    ],
                }

            y = self._yt_dlp
            with y.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except y.utils.DownloadCancelled:
                    self._cleanup_partial()
                    self._queue_event("canceled")
                    return

            self._queue_event("done")

        except Exception as e:
            if self.cancel_requested:
                self._cleanup_partial()
                self._queue_event("canceled")
                return
            self._queue_event("error", str(e))

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
            self._queue_event("downloaded_file", d.get("filename") or info.get("_filename"))
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
                    import subprocess
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
                import subprocess
                if sys.platform == "darwin":
                    subprocess.run(["open", folder])
                else:
                    subprocess.run(["xdg-open", folder])
            except Exception:
                pass
        except Exception:
            pass

    def _finish_ok(self):
        self.status.config(text=self.status.cget("text") or "Download concluído!")
        self.open_folder_button.config(state=NORMAL)
        self.download_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)

    def _finish_canceled(self):
        self.status.config(text="Download cancelado.")
        self.progress["value"] = 0
        self.open_folder_button.config(state=DISABLED)
        self.download_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)
        self.on_status("Download cancelado")

    def _finish_error(self, msg):
        self.status.config(text=msg or "Erro no download.")
        self.download_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)
        self.open_folder_button.config(state=DISABLED)
        self.on_status(f"Erro: {msg or 'falha no download'}")
