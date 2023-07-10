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

# Define um estilo para os widgets
style = ttk.Style()
style.configure("TButton", padding=10, font=("Arial", 12))
style.configure("TLabel", padding=10, font=("Arial", 12))
style.configure("TEntry", padding=10, font=("Arial", 12))

# Cria os widgets da interface
numero_rifa_label = ttk.Label(window, text="Número da Rifa:")
numero_rifa_label.grid(row=0, column=0)
numero_rifa_entry = ttk.Entry(window)
numero_rifa_entry.grid(row=0, column=1)

nome_label = ttk.Label(window, text="Nome:")
nome_label.grid(row=1, column=0)
nome_entry = ttk.Entry(window)
nome_entry.grid(row=1, column=1)

telefone_label = ttk.Label(window, text="Telefone:")
telefone_label.grid(row=2, column=0)
telefone_entry = ttk.Entry(window)
telefone_entry.grid(row=2, column=1)

endereco_label = ttk.Label(window, text="Quem vendeu:")
endereco_label.grid(row=3, column=0)
endereco_entry = ttk.Entry(window)
endereco_entry.grid(row=3, column=1)

vender_button = ttk.Button(window, text="Vender Rifa", command=vender_rifa)
vender_button.grid(row=4, column=0, columnspan=2)

mostrar_rifas_button = ttk.Button(window, text="Mostrar Rifas Vendidas", command=mostrar_rifas)
mostrar_rifas_button.grid(row=5, column=0, columnspan=2)

sortear_rifa_button = ttk.Button(window, text="Sortear Rifa", command=sortear_rifa)
sortear_rifa_button.grid(row=6, column=0, columnspan=2)

numero_rifa_ver_label = ttk.Label(window, text="Número da Rifa:")
numero_rifa_ver_label.grid(row=7, column=0)
numero_rifa_ver_entry = ttk.Entry(window)
numero_rifa_ver_entry.grid(row=7, column=1)

exibir_informacoes_button = ttk.Button(window, text="Exibir Informações", command=exibir_informacoes)
exibir_informacoes_button.grid(row=8, column=0, columnspan=2)

numero_rifa_apagar_label = ttk.Label(window, text="Número da Rifa:")
numero_rifa_apagar_label.grid(row=9, column=0)
numero_rifa_apagar_entry = ttk.Entry(window)
numero_rifa_apagar_entry.grid(row=9, column=1)

apagar_rifa_button = ttk.Button(window, text="Apagar Rifa", command=apagar_rifa)
apagar_rifa_button.grid(row=10, column=0, columnspan=2)

# Inicia o loop principal da janela
window.mainloop()
