rifas = {}

def vender_rifa(numero_rifa, nome, telefone, endereco):
    if numero_rifa in rifas:
        print("Desculpe, essa rifa já foi vendida.")
    else:
        rifas[numero_rifa] = {
            "nome": nome,
            "telefone": telefone,
            "endereco": endereco
        }
        print("Rifa vendida com sucesso!")

def mostrar_rifas():
    for numero_rifa, comprador in rifas.items():
        print(f"Número da rifa: {numero_rifa}")
        print(f"Nome: {comprador['nome']}")
        print(f"Telefone: {comprador['telefone']}")
        print(f"Endereço: {comprador['endereco']}")
        print("--------------------------")

# Exemplo de uso
vender_rifa(1, "João da Silva", "123456789", "Rua A, 123")
vender_rifa(2, "Maria Souza", "987654321", "Avenida B, 456")
vender_rifa(1, "José Pereira", "555555555", "Rua C, 789")  # Tentando vender uma rifa já vendida

mostrar_rifas()