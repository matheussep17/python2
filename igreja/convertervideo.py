import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import os
import subprocess
import sys


class VideoConverterApp(ttk.Window):
    def __init__(self):
        super().__init__(title="Conversor de Vídeo", themename="darkly", size=(600, 300))
        self.center_window(600, 300)
        self.caminho_video = ""
        self.ultimo_arquivo_convertido = ""
        self.formato_destino = tk.StringVar(value="mp4")
        self.init_ui()

    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def init_ui(self):
        ttk.Label(self, text="Conversor de Vídeo", font=("Helvetica", 20, "bold")).pack(pady=(20, 10))

        ttk.Button(
            self,
            text="Selecionar Vídeo",
            command=self.selecionar_video,
            bootstyle=WARNING,
        ).pack(pady=10)

        self.label_video = ttk.Label(self, text="Nenhum arquivo selecionado", font=("Helvetica", 12))
        self.label_video.pack()

        self.label_formato = ttk.Label(self, text="", font=("Helvetica", 12))
        self.label_formato.pack()

        ttk.Label(self, text="Converter para:", font=("Helvetica", 14, "bold")).pack(pady=(15, 5))
        self.format_menu = ttk.Combobox(
            self,
            textvariable=self.formato_destino,
            values=["mp4", "avi", "mkv", "mov"],
            state="readonly",
        )
        self.format_menu.pack()

        ttk.Button(
            self,
            text="Converter",
            command=self.converter_video,
            bootstyle=SUCCESS,
        ).pack(pady=10)

        self.open_btn = ttk.Button(
            self,
            text="Abrir pasta do arquivo convertido",
            command=self.abrir_pasta,
            bootstyle=INFO,
            state=DISABLED,
        )
        self.open_btn.pack(pady=10)

    def selecionar_video(self):
        caminho = filedialog.askopenfilename(
            title="Selecione um vídeo",
            filetypes=[("Arquivos de vídeo", "*.mp4 *.avi *.mkv *.mov *.webm")],
        )
        if caminho:
            self.caminho_video = caminho
            formato_original = os.path.splitext(caminho)[1][1:].lower()
            self.label_video.config(text=f"Arquivo selecionado: {os.path.basename(caminho)}")
            self.label_formato.config(text=f"Formato original: {formato_original}")

    def converter_video(self):
        if not self.caminho_video:
            messagebox.showerror("Erro", "Selecione um vídeo primeiro.")
            return

        formato_destino = self.formato_destino.get()
        pasta_saida = os.path.dirname(self.caminho_video)
        nome_saida = os.path.splitext(os.path.basename(self.caminho_video))[0] + f".{formato_destino}"
        caminho_saida = os.path.join(pasta_saida, nome_saida)

        try:
            comando = ["ffmpeg", "-i", self.caminho_video, caminho_saida]
            subprocess.run(comando, check=True)
            messagebox.showinfo("Sucesso", f"Vídeo convertido para {formato_destino} com sucesso!")
            self.ultimo_arquivo_convertido = caminho_saida
            self.open_btn.config(state=NORMAL)
        except subprocess.CalledProcessError:
            messagebox.showerror("Erro", "Falha na conversão.")

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
                messagebox.showerror("Erro", f"Não foi possível abrir a pasta: {e}")
        else:
            messagebox.showerror("Erro", "Nenhum arquivo convertido encontrado.")


if __name__ == "__main__":
    app = VideoConverterApp()
    app.mainloop()