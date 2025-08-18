# igreja/baixarmusica.py
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import yt_dlp
import json
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import os
import math

CONFIG_FILE = Path("config.json")


def format_bytes(n):
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
        super().__init__(title="Baixar vídeos e músicas do YouTube",
                         themename="darkly", size=(680, 420))
        self.center_window(680, 420)
        self.destination_folder = self.load_config()
        self.selected_format = tk.StringVar(value="mp3")
        self.selected_quality = tk.StringVar(value="best")
        self.downloaded_file = None
        self._last_logged_percent = -1  # só para limitar updates de UI

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

        ttk.Label(main, text="Formato:", font=("Helvetica", 14)).grid(
            row=3, column=0, padx=5, pady=5, sticky="e"
        )
        self.format_menu = ttk.Combobox(
            main, textvariable=self.selected_format, values=["mp3", "mp4"],
            state="readonly", font=("Helvetica", 12)
        )
        self.format_menu.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(main, text="Qualidade:", font=("Helvetica", 14)).grid(
            row=3, column=2, padx=5, pady=5, sticky="e"
        )
        self.quality_menu = ttk.Combobox(
            main, textvariable=self.selected_quality,
            values=["best", "144p", "240p", "360p", "480p", "720p", "1080p", "1440p", "2160p"],
            state="readonly", font=("Helvetica", 12)
        )
        self.quality_menu.grid(row=3, column=3, padx=5, pady=5, sticky="w")

        ttk.Button(
            main, text="Baixar", command=self.start_download, bootstyle=PRIMARY
        ).grid(row=4, column=0, columnspan=4, pady=(15, 5), sticky="ew")

        # Barra de progresso (somente percent)
        self.progress = ttk.Progressbar(main, orient=tk.HORIZONTAL, length=400, mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=4, pady=6, sticky="ew")

        # Status enxuto (sem ETA / sem N/A)
        self.status = ttk.Label(main, text="", font=("Helvetica", 12))
        self.status.grid(row=6, column=0, columnspan=4, pady=(0, 10), sticky="ew")

        self.open_folder_button = ttk.Button(
            main, text="Abrir local do arquivo",
            command=self.open_file_location, bootstyle=INFO, state=DISABLED
        )
        self.open_folder_button.grid(row=7, column=0, columnspan=4)

        for i in range(4):
            main.columnconfigure(i, weight=1)

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

    def start_download(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Erro", "Insira a URL do YouTube.")
            return
        if not self.destination_folder:
            messagebox.showerror("Erro", "Escolha a pasta de destino.")
            return

        # reset UI
        self.progress["value"] = 0
        self.status.config(text="")
        self._last_logged_percent = -1
        self.open_folder_button.config(state=DISABLED)
        self.downloaded_file = None

        threading.Thread(
            target=self.download_media,
            args=(url, self.selected_format.get(), self.selected_quality.get()),
            daemon=True,
        ).start()

    def download_media(self, url, format_choice, quality_choice):
        try:
            self.status.config(text="Preparando...")

            if format_choice == "mp3":
                # áudio: extrai em MP3 via ffmpeg
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
                }
            else:
                # vídeo MP4 com AAC (evita Opus):
                # escolhe trilhas compatíveis: vídeo mp4 (H.264) + áudio m4a (AAC)
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
                    "merge_output_format": "mp4",  # garante contêiner mp4
                }
                # Se ainda assim pegar áudio incompatível em casos raros,
                # descomente as linhas abaixo para forçar reencode do áudio para AAC:
                # ydl_opts["postprocessor_args"] = ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.status.config(text="Download concluído!")
            self.open_folder_button.config(state=NORMAL)

        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def ydl_hook(self, d):
        if d.get("status") == "finished":
            self.progress["value"] = 100
            self.status.config(text="Concluído!")
            self.downloaded_file = d.get("filename") or d.get("info_dict", {}).get("_filename")
            return

        if d.get("status") == "downloading":
            downloaded = d.get("downloaded_bytes")
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            speed = d.get("speed")  # manteremos na UI (sem ETA)

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

            # Status sem ETA e sem 'N/A'
            self.status.config(text=" • ".join([p for p in parts if p]))

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
