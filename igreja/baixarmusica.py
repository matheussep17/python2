# igreja/baixarmusica.py
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import yt_dlp
from yt_dlp.utils import DownloadCancelled
import json
from pathlib import Path
import subprocess
import sys
import os
import math

CONFIG_FILE = Path("config.json")


def format_bytes(n):
    """Formata bytes em unidades legíveis (KB/MB/GB)."""
    try:
        n = float(n)
    except Exception:
        return None
    if n <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = min(int(math.log(n, 1024)), len(units) - 1)
    val = n / (1024 ** idx)
    return (f"{val:,.0f}" if val >= 100 else f"{val:,.2f}").replace(",", ".") + f" {units[idx]}"


class YouTubeDownloaderApp(ttk.Window):
    def __init__(self):
        # janelinha um pouco maior para caber o texto "Qualidade do vídeo"
        super().__init__(title="Baixar vídeos e músicas do YouTube",
                         themename="darkly", size=(780, 460))
        self.center_window(780, 460)

        # estado
        self.destination_folder = self.load_config()
        self.selected_format = tk.StringVar(value="Música")   # antes: "mp3"
        self.selected_quality = tk.StringVar(value="best")
        self.downloaded_file = None

        # controle de cancelamento
        self.cancel_requested = False
        self._last_tmp_file = None  # arquivo parcial (.part) rastreado pelo hook

        self.init_ui()

    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def init_ui(self):
        main = ttk.Frame(self, padding=20)
        main.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        ttk.Label(
            main, text="Baixar Vídeos e Músicas do YouTube",
            font=("Helvetica", 22, "bold")
        ).grid(row=0, column=0, columnspan=4, pady=(0, 10))

        ttk.Label(main, text="YouTube URL:", font=("Helvetica", 14)).grid(
            row=1, column=0, padx=5, pady=5, sticky="e"
        )
        self.url_entry = ttk.Entry(main, width=60, font=("Helvetica", 12))
        self.url_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="we")

        ttk.Button(
            main, text="Escolher pasta de destino",
            command=self.choose_dest_folder, bootstyle=SUCCESS
        ).grid(row=2, column=0, padx=5, pady=5, sticky="e")

        self.dest_label = ttk.Label(
            main, text=self.destination_folder or "Nenhuma pasta selecionada",
            width=50, anchor="w", font=("Helvetica", 12)
        )
        self.dest_label.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="we")

        # Formato (Música/Vídeo)
        ttk.Label(main, text="Formato:", font=("Helvetica", 14)).grid(
            row=3, column=0, padx=5, pady=5, sticky="e"
        )
        self.format_menu = ttk.Combobox(
            main, textvariable=self.selected_format,
            values=["Música", "Vídeo"],              # antes: ["mp3", "mp4"]
            state="readonly", font=("Helvetica", 12), width=12
        )
        self.format_menu.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        self.format_menu.bind("<<ComboboxSelected>>", self._on_format_change)

        # Qualidade do vídeo (mostrada apenas quando formato = Vídeo)
        self.quality_label = ttk.Label(main, text="Qualidade do vídeo:", font=("Helvetica", 14))
        self.quality_label.grid(row=3, column=2, padx=5, pady=5, sticky="e")

        self.quality_menu = ttk.Combobox(
            main, textvariable=self.selected_quality,
            values=["best", "144p", "240p", "360p", "480p",
                    "720p", "1080p", "1440p", "2160p"],
            state="readonly", font=("Helvetica", 12), width=12
        )
        self.quality_menu.grid(row=3, column=3, padx=5, pady=5, sticky="w")

        # referências diretas (sem grid_slaves)
        self._quality_widgets = [self.quality_label, self.quality_menu]

        # Ações
        actions = ttk.Frame(main)
        actions.grid(row=4, column=0, columnspan=4, pady=(15, 8), sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        self.download_btn = ttk.Button(actions, text="Baixar",
                                       command=self.start_download, bootstyle=PRIMARY)
        self.download_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.cancel_btn = ttk.Button(actions, text="Cancelar",
                                     command=self.cancel_download,
                                     bootstyle=SECONDARY, state=DISABLED)
        self.cancel_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # Barra de progresso + status (sem ETA / sem log)
        self.progress = ttk.Progressbar(main, orient=tk.HORIZONTAL,
                                        length=400, mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=4, pady=6, sticky="ew")

        self.status = ttk.Label(main, text="", font=("Helvetica", 12))
        self.status.grid(row=6, column=0, columnspan=4, pady=(0, 12), sticky="ew")

        self.open_folder_button = ttk.Button(
            main, text="Abrir local do arquivo",
            command=self.open_file_location, bootstyle=INFO, state=DISABLED
        )
        self.open_folder_button.grid(row=7, column=0, columnspan=4)

        for i in range(4):
            main.columnconfigure(i, weight=1)

        # aplica a visibilidade inicial (default é "Música" → esconde qualidade)
        self._apply_quality_visibility()

    # ---------- Config ----------
    def load_config(self):
        if CONFIG_FILE.exists():
            with CONFIG_FILE.open("r", encoding="utf-8") as file:
                return json.load(file).get("destination_folder", "")
        return ""

    def save_config(self):
        with CONFIG_FILE.open("w", encoding="utf-8") as file:
            json.dump({"destination_folder": self.destination_folder}, file)

    def choose_dest_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.destination_folder = folder
            self.dest_label.config(text=folder)
            self.save_config()

    # ---------- Eventos UI ----------
    def _on_format_change(self, _evt=None):
        self._apply_quality_visibility()

    def _is_video(self):
        return self.selected_format.get() == "Vídeo"

    def _apply_quality_visibility(self):
        # mostra qualidade somente quando o formato é "Vídeo"
        if self._is_video():
            for w in self._quality_widgets:
                try:
                    w.grid()
                except Exception:
                    pass
        else:
            for w in self._quality_widgets:
                try:
                    w.grid_remove()
                except Exception:
                    pass

    # ---------- Download ----------
    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Erro", "Insira a URL do YouTube.")
            return
        if not self.destination_folder:
            messagebox.showerror("Erro", "Escolha a pasta de destino.")
            return

        # reset UI
        self.progress["value"] = 0
        self.status.config(text="Preparando...")
        self.open_folder_button.config(state=DISABLED)
        self.downloaded_file = None
        self.cancel_requested = False
        self._last_tmp_file = None

        # travar/soltar botões
        self.download_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)

        fmt_mode = self.selected_format.get()   # "Música" ou "Vídeo"
        qual = self.selected_quality.get()

        threading.Thread(
            target=self.download_media,
            args=(url, fmt_mode, qual),
            daemon=True,
        ).start()

    def cancel_download(self):
        if self.cancel_requested:
            return
        self.cancel_requested = True
        self.cancel_btn.config(state=DISABLED)
        self.status.config(text="Cancelando...")

    def _cleanup_partial(self):
        """Remove arquivo parcial conhecido (.part / .ytdl)."""
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
            if fmt_mode == "Música":
                # áudio -> MP3
                ydl_opts = {
                    "format": "bestaudio/best",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                    }],
                    "outtmpl": os.path.join(self.destination_folder, "%(title)s.%(ext)s"),
                    "progress_hooks": [self.ydl_hook],
                    "noprogress": True,
                    "nocolor": True,
                    "quiet": True,
                }
            else:
                # vídeo MP4 (H.264) + m4a (AAC)
                if quality_choice == "best":
                    vsel = "bestvideo[ext=mp4]"
                else:
                    h = "".join(ch for ch in quality_choice if ch.isdigit()) or "1080"
                    vsel = f"bestvideo[ext=mp4][height<={h}]"
                fmt = f"{vsel}+bestaudio[ext=m4a]/best[ext=mp4]/best"

                ydl_opts = {
                    "format": fmt,
                    "outtmpl": os.path.join(self.destination_folder, "%(title)s.%(ext)s"),
                    "progress_hooks": [self.ydl_hook],
                    "noprogress": True,
                    "nocolor": True,
                    "quiet": True,
                    "merge_output_format": "mp4",
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except DownloadCancelled:
                    # cancelado pelo usuário
                    self._cleanup_partial()
                    self._finish_canceled()
                    return

            # concluído
            self._finish_ok()

        except Exception as e:
            if self.cancel_requested:
                # Tratamento gentil se a exceção veio após cancelar
                self._cleanup_partial()
                self._finish_canceled()
                return
            self._finish_error(str(e))

    # ---------- Hooks / Finalização ----------
    def ydl_hook(self, d):
        # cancelar de forma amigável
        if self.cancel_requested:
            raise DownloadCancelled()

        status = d.get("status")
        # Guarda caminho temporário/definitivo para poder limpar em cancelamento
        self._last_tmp_file = d.get("tmpfilename") or d.get("filename") or self._last_tmp_file

        if status == "finished":
            self.progress["value"] = 100
            self.status.config(text="Concluído!")
            self.downloaded_file = d.get("filename") or d.get("info_dict", {}).get("_filename")
            return

        if status == "downloading":
            downloaded = d.get("downloaded_bytes")
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            speed = d.get("speed")  # mostrado sem ETA

            pct = None
            if downloaded is not None and total:
                try:
                    pct = max(0.0, min(100.0, (downloaded / total) * 100.0))
                except Exception:
                    pct = None

            if pct is not None:
                self.progress["value"] = pct

            parts = ["Baixando..."]
            if pct is not None:
                parts.append(f"{pct:.1f}%")
            if downloaded is not None:
                if total:
                    parts.append(f"({format_bytes(downloaded)} de {format_bytes(total)})")
                else:
                    parts.append(f"({format_bytes(downloaded)})")
            if speed:
                sp = format_bytes(speed)
                if sp:
                    parts.append(f"{sp}/s")

            self.status.config(text=" • ".join([p for p in parts if p]))

    def _finish_ok(self):
        self.status.config(text="Download concluído!")
        self.open_folder_button.config(state=NORMAL)
        self.download_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)

    def _finish_canceled(self):
        self.status.config(text="Download cancelado.")
        self.progress["value"] = 0
        self.open_folder_button.config(state=DISABLED)
        self.download_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)

    def _finish_error(self, msg):
        self.status.config(text="")
        self.download_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)
        messagebox.showerror("Erro", msg)

    # ---------- Abertura de pasta ----------
    def open_file_location(self):
        if self.downloaded_file:
            file_dir = os.path.dirname(self.downloaded_file)
            try:
                if sys.platform.startswith("win"):
                    os.startfile(file_dir)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", file_dir])
                else:
                    subprocess.Popen(["xdg-open", file_dir])
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível abrir o local do arquivo: {e}")
        else:
            messagebox.showerror("Erro", "Nenhum arquivo baixado encontrado.")


if __name__ == "__main__":
    app = YouTubeDownloaderApp()
    app.mainloop()
