import sqlite3

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
def vender_rifa(numero_rifa, nome, telefone, endereco):
    conn = sqlite3.connect("rifas.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rifas WHERE numero_rifa = ?", (numero_rifa,))
    rifa = cursor.fetchone()
    if rifa:
        print("Desculpe, essa rifa já foi vendida.")
    else:
        cursor.execute("INSERT INTO rifas VALUES (?, ?, ?, ?)", (numero_rifa, nome, telefone, endereco))
        conn.commit()
        print("Rifa vendida com sucesso!")
    conn.close()

# Função para mostrar todas as rifas vendidas
def mostrar_rifas():
    conn = sqlite3.connect("rifas.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rifas")
    rifas = cursor.fetchall()
    conn.close()

    if rifas:
        for rifa in rifas:
            numero_rifa, nome, telefone, endereco = rifa
            print(f"Número da rifa: {numero_rifa}")
            print(f"Nome: {nome}")
            print(f"Telefone: {telefone}")
            print(f"Endereço: {endereco}")
            print("--------------------------")
    else:
        print("Nenhuma rifa vendida.")

# Cria a tabela de rifas no banco de dados (executar somente na primeira execução)
criar_tabela_rifas()

def limpar_rifas():
    conn = sqlite3.connect("rifas.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rifas")
    conn.commit()
    conn.close()
    print("Todas as rifas foram removidas.")

#Exemplo de uso
#vender_rifa(1, "João da Silva", "123456789", "Rua A, 123")
#vender_rifa(2, "Maria Souza", "987654321", "Avenida B, 456")
#vender_rifa(1, "José Pereira", "555555555", "Rua C, 789")  # Tentando vender uma rifa já vendida

mostrar_rifas()
#limpar_rifas()