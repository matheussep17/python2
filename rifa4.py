import random
import sqlite3
import tkinter as tk
from tkinter import messagebox

# Função para limpar rifas
def limpar_rifas():
    conn = sqlite3.connect("rifas.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rifas")
    conn.commit()
    conn.close()
    messagebox.showinfo("Sucesso", "Todas as rifas foram limpas com sucesso!")


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

# Cria a tabela de rifas no banco de dados (executar somente na primeira execução)
criar_tabela_rifas()

# Cria a janela principal
window = tk.Tk()
window.title("Sistema de Venda de Rifas")

# Cria os widgets da interface
numero_rifa_label = tk.Label(window, text="Número da Rifa:")
numero_rifa_label.pack()
numero_rifa_entry = tk.Entry(window)
numero_rifa_entry.pack()

nome_label = tk.Label(window, text="Nome:")
nome_label.pack()
nome_entry = tk.Entry(window)
nome_entry.pack()

telefone_label = tk.Label(window, text="Telefone:")
telefone_label.pack()
telefone_entry = tk.Entry(window)
telefone_entry.pack()

endereco_label = tk.Label(window, text="Endereço:")
endereco_label.pack()
endereco_entry = tk.Entry(window)
endereco_entry.pack()

vender_button = tk.Button(window, text="Vender Rifa", command=vender_rifa)
vender_button.pack()

mostrar_rifas_button = tk.Button(window, text="Mostrar Rifas Vendidas", command=mostrar_rifas)
mostrar_rifas_button.pack()

sortear_rifa_button = tk.Button(window, text="Sortear Rifa", command=sortear_rifa)
sortear_rifa_button.pack()

limpar_rifas_button = tk.Button(window, text="Limpar Rifas", command=limpar_rifas)
limpar_rifas_button.pack()
# Inicia o loop principal da interface gráfica
window.mainloop()
