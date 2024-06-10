import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import yt_dlp
import json
from datetime import datetime
import os

CONFIG_FILE = 'config.json'

class YouTubeDownloaderApp(ttk.Window):
    def __init__(self):
        super().__init__(title="Baixar vídeos e músicas do YouTube", themename="superhero", size=(600, 500))
        self.destination_folder = self.load_config()
        self.selected_format = tk.StringVar(value="mp3")  # Define MP3 como padrão
        self.selected_quality = tk.StringVar(value="best")  # Define qualidade como padrão
        self.downloaded_file = None
        self.init_ui()

    def init_ui(self):
        self.header = ttk.Label(self, text="Baixar Vídeos e Músicas do YouTube", font=('Helvetica', 20, 'bold'))
        self.header.grid(row=0, column=0, columnspan=3, pady=20)

        self.url_label = ttk.Label(self, text="YouTube URL:", font=('Helvetica', 12))
        self.url_label.grid(row=1, column=0, padx=5, sticky='w')

        self.url_entry = ttk.Entry(self, width=50, font=('Helvetica', 12))
        self.url_entry.grid(row=1, column=1, padx=5)

        self.dest_button = ttk.Button(self, text="Escolher pasta de destino", command=self.choose_dest_folder, bootstyle=SUCCESS)
        self.dest_button.grid(row=2, column=0, padx=5, pady=10, sticky='w')

        self.dest_label = ttk.Label(self, text=self.destination_folder or "Nenhuma pasta selecionada", width=30, anchor='w', font=('Helvetica', 12))
        self.dest_label.grid(row=2, column=1, padx=5, pady=10, sticky='w')

        self.format_label = ttk.Label(self, text="Formato:", font=('Helvetica', 12))
        self.format_label.grid(row=3, column=0, padx=5, sticky='w')

        self.format_menu = ttk.Combobox(self, textvariable=self.selected_format, values=['mp3', 'mp4'], state='readonly')
        self.format_menu.grid(row=3, column=1, padx=5, pady=10)

        self.quality_label = ttk.Label(self, text="Qualidade:", font=('Helvetica', 12))
        self.quality_label.grid(row=4, column=0, padx=5, sticky='w')

        self.quality_menu = ttk.Combobox(self, textvariable=self.selected_quality, values=['best', '144p', '240p', '360p', '480p', '720p', '1080p', '1440p', '2160p'], state='readonly')
        self.quality_menu.grid(row=4, column=1, padx=5, pady=10)

        self.download_button = ttk.Button(self, text="Baixar", command=self.start_download, bootstyle=PRIMARY)
        self.download_button.grid(row=5, column=0, columnspan=3, pady=10)

        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.progress.grid(row=6, column=0, columnspan=3, pady=10)

        self.stats_label = ttk.Label(self, text="", font=('Helvetica', 12))
        self.stats_label.grid(row=7, column=0, columnspan=3, pady=10)

        self.log_text = ScrolledText(self, height=8, state='disabled', wrap='word', font=('Helvetica', 10))
        self.log_text.grid(row=8, column=0, columnspan=3, pady=10, padx=10, sticky='nsew')

        self.open_folder_button = ttk.Button(self, text="Abrir local do arquivo", command=self.open_file_location, bootstyle=INFO)
        self.open_folder_button.grid(row=9, column=0, columnspan=3, pady=10)
        self.open_folder_button.grid_remove()  # Initially hide the button

        self.init_menu()

        self.grid_columnconfigure(1, weight=1)  # Make the second column expand

    def init_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Sobre", command=self.show_about)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.quit)
        menubar.add_cascade(label="Arquivo", menu=file_menu)
        self.config(menu=menubar)

    def show_about(self):
        messagebox.showinfo("Sobre", "Tava sem ideia mas é isso ai")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as file:
                config = json.load(file)
                return config.get('destination_folder', '')
        return ''

    def save_config(self):
        with open(CONFIG_FILE, 'w') as file:
            config = {'destination_folder': self.destination_folder}
            json.dump(config, file)

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

        format_choice = self.selected_format.get()
        quality_choice = self.selected_quality.get()
        threading.Thread(target=self.download_media, args=(url, format_choice, quality_choice)).start()

    def download_media(self, url, format_choice, quality_choice):
        try:
            self.progress['value'] = 0
            if format_choice == 'mp3':
                self.stats_label.config(text="Baixando áudio...")
                self.log("Baixando áudio...")
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': format_choice,
                    }],
                    'outtmpl': os.path.join(self.destination_folder, '%(title)s.%(ext)s'),
                    'progress_hooks': [self.ydl_hook],
                    'noprogress': False,
                    'nocolor': True,
                }
            elif format_choice == 'mp4':
                self.stats_label.config(text="Baixando vídeo...")
                self.log("Baixando vídeo...")
                if quality_choice == 'best':
                    ydl_opts = {
                        'format': 'bestvideo+bestaudio/best',
                        'outtmpl': os.path.join(self.destination_folder, '%(title)s.%(ext)s'),
                        'progress_hooks': [self.ydl_hook],
                        'noprogress': False,
                        'nocolor': True,
                    }
                else:
                    ydl_opts = {
                        'format': f'bestvideo[height<={quality_choice[:-1]}]+bestaudio/best',
                        'outtmpl': os.path.join(self.destination_folder, '%(title)s.%(ext)s'),
                        'progress_hooks': [self.ydl_hook],
                        'noprogress': False,
                        'nocolor': True,
                    }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.download([url])

            self.stats_label.config(text="Download Concluído!")
            self.log("Download Concluído!")
            self.open_folder_button.grid()
        except Exception as e:
            self.log(f"Erro: {str(e)}")
            messagebox.showerror("Erro", str(e))

    def ydl_hook(self, d):
        if d['status'] == 'finished':
            self.progress['value'] = 100
            self.stats_label.config(text="Concluído!")
            self.log("Concluído!")
            self.downloaded_file = d['filename']  # Save the downloaded file path
        elif d['status'] == 'downloading':
            p_str = d.get('_percent_str', '0.0%').replace('%', '').strip()
            try:
                p = float(p_str)
                self.progress['value'] = p
            except ValueError:
                p = 0
            self.stats_label.config(text=f"Baixando: {d['_percent_str']} de {d.get('_total_bytes_str', 'N/A')} a {d.get('_speed_str', 'N/A')} ETA: {d.get('_eta_str', 'N/A')}")
            self.log(f"Baixando: {d['_percent_str']} de {d.get('_total_bytes_str', 'N/A')} a {d.get('_speed_str', 'N/A')} ETA: {d.get('_eta_str', 'N/A')}")

    def log(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.log_text.config(state='disabled')
        self.log_text.yview(tk.END)

    def open_file_location(self):
        if self.downloaded_file:
            file_dir = os.path.dirname(self.downloaded_file)
            os.startfile(file_dir)
        else:
            messagebox.showerror("Erro", "Nenhum arquivo baixado encontrado.")

if __name__ == "__main__":
    app = YouTubeDownloaderApp()
    app.mainloop()
