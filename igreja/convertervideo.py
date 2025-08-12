import tkinter as tk
from tkinter import filedialog, messagebox
import os
import subprocess

# Função para selecionar vídeo
def selecionar_video():
    global caminho_video, formato_original
    caminho_video = filedialog.askopenfilename(
        title="Selecione um vídeo",
        filetypes=[("Arquivos de vídeo", "*.mp4 *.avi *.mkv *.mov *.webm")]
    )
    if caminho_video:
        formato_original = os.path.splitext(caminho_video)[1][1:].lower()
        label_video.config(text=f"Arquivo selecionado: {os.path.basename(caminho_video)}")
        label_formato.config(text=f"Formato original: {formato_original}")

# Função para converter vídeo
def converter_video():
    if not caminho_video:
        messagebox.showerror("Erro", "Selecione um vídeo primeiro.")
        return
    
    formato_destino = combo_formato.get()
    pasta_saida = os.path.dirname(caminho_video)
    nome_saida = os.path.splitext(os.path.basename(caminho_video))[0] + f".{formato_destino}"
    caminho_saida = os.path.join(pasta_saida, nome_saida)
    
    try:
        comando = ["ffmpeg", "-i", caminho_video, caminho_saida]
        subprocess.run(comando, check=True)
        messagebox.showinfo("Sucesso", f"Vídeo convertido para {formato_destino} com sucesso!")
        global ultimo_arquivo_convertido
        ultimo_arquivo_convertido = caminho_saida
    except subprocess.CalledProcessError:
        messagebox.showerror("Erro", "Falha na conversão.")

# Função para abrir a pasta do arquivo convertido
def abrir_pasta():
    if ultimo_arquivo_convertido and os.path.exists(ultimo_arquivo_convertido):
        pasta = os.path.dirname(ultimo_arquivo_convertido)
        os.startfile(pasta)
    else:
        messagebox.showerror("Erro", "Nenhum arquivo convertido encontrado.")

# Variáveis globais
caminho_video = ""
formato_original = ""
ultimo_arquivo_convertido = ""

# Criar janela
janela = tk.Tk()
janela.title("Conversor de Vídeo")
janela.geometry("500x350")
janela.configure(bg="#1e1e2e")  # Fundo igual ao do app de música

# Estilo de fonte
fonte_titulo = ("Arial", 14, "bold")
fonte_texto = ("Arial", 11)

# Botão selecionar vídeo
btn_selecionar = tk.Button(janela, text="Selecionar Vídeo", font=fonte_texto, bg="#ff9800", fg="white", command=selecionar_video)
btn_selecionar.pack(pady=10)

# Labels
label_video = tk.Label(janela, text="Nenhum arquivo selecionado", font=fonte_texto, bg="#1e1e2e", fg="white")
label_video.pack()

label_formato = tk.Label(janela, text="", font=fonte_texto, bg="#1e1e2e", fg="white")
label_formato.pack()

# Seletor de formato
tk.Label(janela, text="Converter para:", font=fonte_titulo, bg="#1e1e2e", fg="#00e676").pack(pady=5)
combo_formato = tk.StringVar(janela)
combo_formato.set("mp4")
opcoes = tk.OptionMenu(janela, combo_formato, "mp4", "avi", "mkv", "mov")
opcoes.config(font=fonte_texto, bg="#424242", fg="white")
opcoes.pack()

# Botão converter
btn_converter = tk.Button(janela, text="Converter", font=fonte_texto, bg="#4caf50", fg="white", command=converter_video)
btn_converter.pack(pady=10)

# Botão abrir pasta
btn_abrir = tk.Button(janela, text="Abrir pasta do arquivo convertido", font=fonte_texto, bg="#2196f3", fg="white", command=abrir_pasta)
btn_abrir.pack(pady=10)

# Rodar app
janela.mainloop()
