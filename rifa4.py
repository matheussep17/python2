import random
import sqlite3
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

# Função para criar a tabela de rifas no banco de dados
def criar_tabela_rifas():
    conn = sqlite3.connect("rifas.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rifas (
            numero_rifa INTEGER PRIMARY KEY,
            nome TEXT,
            telefone TEXT,
            endereco TEXT
        )
    """)
    conn.commit()
    conn.close()

# Função para vender uma rifa e inserir os dados no banco de dados
def vender_rifa():
    numero_rifa = int(numero_rifa_entry.get())
    nome = nome_entry.get()
    telefone = telefone_entry.get()
    endereco = endereco_entry.get()

    conn = sqlite3.connect("rifas.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rifas WHERE numero_rifa = ?", (numero_rifa,))
    rifa = cursor.fetchone()
    if rifa:
        messagebox.showinfo("Erro", f"A rifa número {numero_rifa} já foi vendida.")
    else:
        cursor.execute("INSERT INTO rifas VALUES (?, ?, ?, ?)", (numero_rifa, nome, telefone, endereco))
        conn.commit()
        messagebox.showinfo("Sucesso", "Rifa vendida com sucesso!")
    conn.close()

# Função para mostrar todas as rifas vendidas
def mostrar_rifas():
    conn = sqlite3.connect("rifas.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rifas")
    rifas = cursor.fetchall()
    conn.close()

    if rifas:
        rifas_text = ""
        for rifa in rifas:
            numero_rifa, nome, telefone, endereco = rifa
            rifas_text += f"Número da rifa: {numero_rifa}\n"
            rifas_text += f"Nome: {nome}\n"
            rifas_text += f"Telefone: {telefone}\n"
            rifas_text += f"Endereço: {endereco}\n"
            rifas_text += "--------------------------\n"
        messagebox.showinfo("Rifas Vendidas", rifas_text)
    else:
        messagebox.showinfo("Rifas Vendidas", "Nenhuma rifa vendida.")

# Função para sortear uma rifa e exibir as informações do comprador correspondente
def sortear_rifa():
    conn = sqlite3.connect("rifas.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rifas")
    rifas = cursor.fetchall()
    conn.close()

    if rifas:
        numero_rifa_sorteada = random.choice(rifas)[0]
        rifas_text = f"A rifa sorteada é a número {numero_rifa_sorteada}.\n\n"

        for rifa in rifas:
            numero_rifa, nome, telefone, endereco = rifa
            if numero_rifa == numero_rifa_sorteada:
                rifas_text += f"Número da rifa: {numero_rifa}\n"
                rifas_text += f"Nome: {nome}\n"
                rifas_text += f"Telefone: {telefone}\n"
                rifas_text += f"Endereço: {endereco}\n"
                rifas_text += "--------------------------\n"
        messagebox.showinfo("Rifa Sorteada", rifas_text)
    else:
        messagebox.showinfo("Rifa Sorteada", "Nenhuma rifa vendida.")

# Função para exibir as informações de uma rifa específica
def exibir_informacoes():
    numero_rifa = int(numero_rifa_ver_entry.get())

    conn = sqlite3.connect("rifas.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rifas WHERE numero_rifa = ?", (numero_rifa,))
    rifa = cursor.fetchone()
    conn.close()

    if rifa:
        numero_rifa, nome, telefone, endereco = rifa
        messagebox.showinfo("Informações da Rifa", f"Número da rifa: {numero_rifa}\nNome: {nome}\nTelefone: {telefone}\nEndereço: {endereco}")
    else:
        messagebox.showinfo("Informações da Rifa", f"A rifa número {numero_rifa} não foi encontrada.")

# Função para apagar uma rifa específica
def apagar_rifa():
    numero_rifa = int(numero_rifa_apagar_entry.get())

    conn = sqlite3.connect("rifas.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rifas WHERE numero_rifa = ?", (numero_rifa,))
    rifa = cursor.fetchone()
    if rifa:
        result = messagebox.askyesno("Apagar Rifa", f"Tem certeza que deseja apagar a rifa número {numero_rifa}?")
        if result == tk.YES:
            cursor.execute("DELETE FROM rifas WHERE numero_rifa = ?", (numero_rifa,))
            conn.commit()
            messagebox.showinfo("Apagar Rifa", f"A rifa número {numero_rifa} foi apagada com sucesso!")
    else:
        messagebox.showinfo("Apagar Rifa", f"A rifa número {numero_rifa} não foi encontrada.")
    conn.close()

# Cria a tabela de rifas no banco de dados (executar somente na primeira execução)
criar_tabela_rifas()

# Cria a janela principal
window = tk.Tk()
window.title("Sistema de Venda de Rifas")
window.geometry("400x500")

# Define um estilo para os widgets
style = ttk.Style()
style.configure("TButton", padding=10, font=("Arial", 12))
style.configure("TLabel", padding=10, font=("Arial", 12))
style.configure("TEntry", padding=10, font=("Arial", 12))

# Cria os widgets da interface
titulo_label = ttk.Label(window, text="Sistema de Venda de Rifas", font=("Arial", 16, "bold"))
titulo_label.pack(pady=10)

numero_rifa_label = ttk.Label(window, text="Número da Rifa:")
numero_rifa_label.pack()
numero_rifa_entry = ttk.Entry(window)
numero_rifa_entry.pack()

nome_label = ttk.Label(window, text="Nome:")
nome_label.pack()
nome_entry = ttk.Entry(window)
nome_entry.pack()

telefone_label = ttk.Label(window, text="Telefone:")
telefone_label.pack()
telefone_entry = ttk.Entry(window)
telefone_entry.pack()

endereco_label = ttk.Label(window, text="Endereço:")
endereco_label.pack()
endereco_entry = ttk.Entry(window)
endereco_entry.pack()

vender_button = ttk.Button(window, text="Vender Rifa", command=vender_rifa)
vender_button.pack(pady=10)

mostrar_rifas_button = ttk.Button(window, text="Mostrar Rifas Vendidas", command=mostrar_rifas)
mostrar_rifas_button.pack(pady=10)

sortear_rifa_button = ttk.Button(window, text="Sortear Rifa", command=sortear_rifa)
sortear_rifa_button.pack(pady=10)

numero_rifa_ver_label = ttk.Label(window, text="Número da Rifa para Ver Informações:")
numero_rifa_ver_label.pack()
numero_rifa_ver_entry = ttk.Entry(window)
numero_rifa_ver_entry.pack()

exibir_informacoes_button = ttk.Button(window, text="Exibir Informações", command=exibir_informacoes)
exibir_informacoes_button.pack(pady=10)

numero_rifa_apagar_label = ttk.Label(window, text="Número da Rifa para Apagar:")
numero_rifa_apagar_label.pack()
numero_rifa_apagar_entry = ttk.Entry(window)
numero_rifa_apagar_entry.pack()

apagar_rifa_button = ttk.Button(window, text="Apagar Rifa", command=apagar_rifa)
apagar_rifa_button.pack(pady=10)

# Inicia o loop principal da interface gráfica
window.mainloop()
