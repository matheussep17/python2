# app/frames/youtube.py
import os
import sys
import json
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

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

class YouTubeFrame(ttk.Frame):
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

        self._build_ui()

        self.ui_queue = queue.Queue()
        self.after(100, self._drain_ui_queue)
        self._apply_quality_visibility()

    def _build_ui(self):
        card = ttk.Frame(self, padding=18, bootstyle="dark")
        card.pack(fill="both", expand=True)

        header = ttk.Frame(card)
        header.pack(fill="x")
        ttk.Label(header, text="Baixar do YouTube", font=("Helvetica", 18, "bold")).pack(side="left")
        ttk.Separator(card).pack(fill="x", pady=12)

        urlrow = ttk.Frame(card)
        urlrow.pack(fill="x")
        ttk.Label(urlrow, text="YouTube URL:", font=("Helvetica", 13)).pack(side="left")
        self.url_entry = ttk.Entry(urlrow, width=60, font=("Helvetica", 12))
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(10, 0))

        dest = ttk.Frame(card)
        dest.pack(fill="x", pady=(10, 0))
        ttk.Button(dest, text="Escolher pasta de destino", command=self.choose_dest_folder, bootstyle=SUCCESS).pack(side="left")
        self.dest_label = ttk.Label(dest, text=self.destination_folder or "Nenhuma pasta selecionada", anchor="w", font=("Helvetica", 12))
        self.dest_label.pack(side="left", fill="x", expand=True, padx=(10, 0))

        opts = ttk.Frame(card)
        opts.pack(fill="x", pady=(10, 0))
        ttk.Label(opts, text="Formato:", font=("Helvetica", 13)).pack(side="left")
        self.format_menu = ttk.Combobox(opts, textvariable=self.selected_format, values=["Música", "Vídeo"], state="readonly", width=12)
        self.format_menu.pack(side="left", padx=(8, 20))
        self.format_menu.bind("<<ComboboxSelected>>", self._on_format_change)

        self.quality_label = ttk.Label(opts, text="Qualidade do vídeo:", font=("Helvetica", 13))
        self.quality_label.pack(side="left")
        self.quality_menu = ttk.Combobox(
            opts,
            textvariable=self.selected_quality,
            values=["best", "144p", "240p", "360p", "480p", "720p", "1080p", "1440p", "2160p"],
            state="readonly",
            width=12
        )
        self.quality_menu.pack(side="left", padx=(8, 0))
        self._quality_widgets = [self.quality_label, self.quality_menu]

        ctl = ttk.Frame(card)
        ctl.pack(fill="x", pady=(14, 8))
        self.download_btn = ttk.Button(ctl, text="▶️ Baixar", command=self.start_download, bootstyle=PRIMARY)
        self.download_btn.pack(side="left")
        self.cancel_btn = ttk.Button(ctl, text="Cancelar", command=self.cancel_download, bootstyle=SECONDARY, state=DISABLED)
        self.cancel_btn.pack(side="left", padx=(10, 0))

        prog = ttk.Frame(card, padding=10, bootstyle="secondary")
        prog.pack(fill="x", pady=(8, 4))
        self.progress = ttk.Progressbar(prog, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x")
        self.status = ttk.Label(prog, text="", font=("Helvetica", 11))
        self.status.pack(anchor="w", pady=(6, 0))

        self.open_folder_button = ttk.Button(card, text="Abrir local do arquivo", command=self.open_file_location, bootstyle=INFO, state=DISABLED)
        self.open_folder_button.pack(pady=8)

    def load_config(self):
        if CONFIG_FILE.exists():
            try:
                with CONFIG_FILE.open("r", encoding="utf-8") as f:
                    return json.load(f).get("destination_folder", "")
            except Exception:
                return ""
        return ""

    def save_config(self):
        try:
            with CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump({"destination_folder": self.destination_folder}, f, ensure_ascii=False, indent=2)
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
        if self._is_video():
            for w in self._quality_widgets:
                try:
                    w.pack()
                except Exception:
                    pass
        else:
            for w in self._quality_widgets:
                try:
                    w.pack_forget()
                except Exception:
                    pass

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
        Retorna uma única string 'format' que:
          1) tenta altura EXATA (mp4 -> qualquer),
          2) depois altura <= alvo (mp4 -> qualquer),
          3) junta com melhor áudio (m4a preferido, senão bestaudio),
          4) e por fim cai para 'best' como último recurso de segurança.
        Isso evita "travar" em 480p mp4 quando existem 720p/1080p em VP9/AV1.
        """
        if quality_choice == "best":
            return "(bv*[ext=mp4]/bv*)+ba[ext=m4a]/ba/b[ext=mp4]/b"

        h = "".join(ch for ch in quality_choice if ch.isdigit()) or "1080"

        fmt = (
            f"((bv*[ext=mp4][height={h}]/bv*[height={h}])"
            f"/(bv*[ext=mp4][height<={h}]/bv*[height<={h}]))"
            f"+(ba[ext=m4a]/ba)"
            f"/b[ext=mp4]/b"
        )
        return fmt

    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Erro", "Insira a URL do YouTube.")
            return
        if not self.destination_folder:
            messagebox.showerror("Erro", "Escolha a pasta de destino.")
            return

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
                ydl_opts = {**common_args, "format": fmt}

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
        self.status.config(text="")
        self.download_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)
        self.on_status("Erro no download")
        messagebox.showerror("Erro", msg)

    def open_file_location(self):
        if self.downloaded_file:
            d = os.path.dirname(self.downloaded_file)
            try:
                if sys.platform.startswith("win"):
                    os.startfile(d)
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", d])
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", d])
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível abrir o local do arquivo: {e}")
        else:
            messagebox.showerror("Erro", "Nenhum arquivo baixado encontrado.")