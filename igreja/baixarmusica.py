# igreja/baixarmusica.py
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import yt_dlp
import json
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import os

CONFIG_FILE = Path("config.json")

class YouTubeDownloaderApp(ttk.Window):
    def __init__(self):
        super().__init__(title="Baixar vídeos e músicas do YouTube",
                         themename="darkly", size=(800, 600))
        self.center_window(800, 600)
        self.destination_folder = self.load_config()
        self.selected_format = tk.StringVar(value="mp3")
        self.selected_quality = tk.StringVar(value="best")
        self.downloaded_file = None
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

        ttk.Label(main,
                  text="Baixar Vídeos e Músicas do YouTube",
                  font=("Helvetica", 24, "bold")).grid(row=0, column=0,
                                                       columnspan=4, pady=(0, 10))

        ttk.Label(main, text="YouTube URL:",
                  font=("Helvetica", 14)).grid(row=1, column=0, padx=5, pady=5,
                                               sticky="e")
        self.url_entry = ttk.Entry(main, width=60, font=("Helvetica", 12))
        self.url_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5,
                            sticky="we")

        ttk.Button(main, text="Escolher pasta de destino",
                   command=self.choose_dest_folder,
                   bootstyle=SUCCESS).grid(row=2, column=0, padx=5, pady=5,
                                           sticky="e")

        self.dest_label = ttk.Label(
            main,
            text=self.destination_folder or "Nenhuma pasta selecionada",
            width=50,
            anchor="w",
            font=("Helvetica", 12),
        )
        self.dest_label.grid(row=2, column=1, columnspan=3, padx=5, pady=5,
                             sticky="we")

        ttk.Label(main, text="Formato:", font=("Helvetica", 14)).grid(
            row=3, column=0, padx=5, pady=5, sticky="e")
        self.format_menu = ttk.Combobox(
            main, textvariable=self.selected_format, values=["mp3", "mp4"],
            state="readonly", font=("Helvetica", 12))
        self.format_menu.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(main, text="Qualidade:", font=("Helvetica", 14)).grid(
            row=3, column=2, padx=5, pady=5, sticky="e")
        self.quality_menu = ttk.Combobox(
            main, textvariable=self.selected_quality,
            values=["best", "144p", "240p", "360p", "480p", "720p",
                    "1080p", "1440p", "2160p"],
            state="readonly", font=("Helvetica", 12))
        self.quality_menu.grid(row=3, column=3, padx=5, pady=5, sticky="w")

        ttk.Button(main, text="Baixar", command=self.start_download,
                   bootstyle=PRIMARY).grid(row=4, column=0, columnspan=4,
                                           pady=(15, 5), sticky="ew")

        self.progress = ttk.Progressbar(main, orient=tk.HORIZONTAL,
                                        length=400, mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=4, pady=5,
                           sticky="ew")

        self.stats_label = ttk.Label(main, text="", font=("Helvetica", 12))
        self.stats_label.grid(row=6, column=0, columnspan=4, pady=5,
                              sticky="ew")

        log_frame = ttk.LabelFrame(main, text="Log", padding=5)
        log_frame.grid(row=7, column=0, columnspan=4, sticky="nsew",
                       pady=5)
        main.rowconfigure(7, weight=1)
        self.log_text = ScrolledText(
            log_frame, height=8, state="disabled", wrap="word",
            font=("Helvetica", 12)
        )
        self.log_text.pack(fill="both", expand=True)

        self.open_folder_button = ttk.Button(
            main,
            text="Abrir local do arquivo",
            command=self.open_file_location,
            bootstyle=INFO,
            state=DISABLED,
        )
        self.open_folder_button.grid(row=8, column=0, columnspan=4,
                                     pady=(10, 0))

        self.init_menu()

        for i in range(4):
            main.columnconfigure(i, weight=1)

    def init_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Sobre", command=self.show_about)
        file_menu.add_separator()
        file_menu.add_command(label="Criador", command=self.show_creator)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.quit)
        menubar.add_cascade(label="Arquivo", menu=file_menu)
        self.config(menu=menubar)

    def show_about(self):
        messagebox.showinfo("Sobre",
                            "Aplicativo para baixar vídeos e músicas do YouTube.")

    def show_creator(self):
        messagebox.showinfo("Criador", "Desenvolvido por Torres")

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

        threading.Thread(
            target=self.download_media,
            args=(url, self.selected_format.get(), self.selected_quality.get()),
            daemon=True,
        ).start()

    def download_media(self, url, format_choice, quality_choice):
        try:
            self.progress["value"] = 0
            if format_choice == "mp3":
                self.stats_label.config(text="Baixando áudio...")
                self.log("Baixando áudio...")
                ydl_opts = {
                    "format": "bestaudio/best",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": format_choice,
                    }],
                    "outtmpl": os.path.join(self.destination_folder,
                                            "%(title)s.%(ext)s"),
                    "progress_hooks": [self.ydl_hook],
                    "noprogress": False,
                    "nocolor": True,
                }
            else:
                self.stats_label.config(text="Baixando vídeo...")
                self.log("Baixando vídeo...")
                if quality_choice == "best":
                    fmt = "bestvideo+bestaudio/best"
                else:
                    fmt = f"bestvideo[height<={quality_choice[:-1]}]+bestaudio/best"
                ydl_opts = {
                    "format": fmt,
                    "outtmpl": os.path.join(self.destination_folder,
                                            "%(title)s.%(ext)s"),
                    "progress_hooks": [self.ydl_hook],
                    "noprogress": False,
                    "nocolor": True,
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.stats_label.config(text="Download Concluído!")
            self.log("Download Concluído!")
            self.open_folder_button.config(state=NORMAL)
        except Exception as e:
            self.log(f"Erro: {e}")
            messagebox.showerror("Erro", str(e))

    def ydl_hook(self, d):
        if d["status"] == "finished":
            self.progress["value"] = 100
            self.stats_label.config(text="Concluído!")
            self.log("Concluído!")
            self.downloaded_file = d["filename"]
        elif d["status"] == "downloading":
            p_str = d.get("_percent_str", "0.0%").replace("%", "").strip()
            try:
                self.progress["value"] = float(p_str)
            except ValueError:
                self.progress["value"] = 0
            self.stats_label.config(
                text=f"Baixando: {d['_percent_str']} de "
                     f"{d.get('_total_bytes_str', 'N/A')} a "
                     f"{d.get('_speed_str', 'N/A')} ETA: {d.get('_eta_str', 'N/A')}"
            )
            self.log(self.stats_label.cget("text"))

    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END,
                             f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.log_text.configure(state="disabled")
        self.log_text.yview(tk.END)

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
                messagebox.showerror("Erro",
                                     f"Não foi possível abrir o local do arquivo: {e}")
        else:
            messagebox.showerror("Erro", "Nenhum arquivo baixado encontrado.")

if __name__ == "__main__":
    app = YouTubeDownloaderApp()
    app.mainloop()
