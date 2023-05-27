def calculate():
    # Recebe as entradas do usuário
    num1 = float(input("Insira o primeiro número: "))
    num2 = float(input("Insira o segundo número: "))
    oper = input("Insira a operação (+, -, *, /): ")

    # Realiza a operação selecionada
    if oper == '+':
        result = num1 + num2
    elif oper == '-':
        result = num1 - num2
    elif oper == '*':
        result = num1 * num2
    elif oper == '/':
        result = num1 / num2
    else:
        result = "Operação inválida"

    # Exibe o resultado na tela
    print("Resultado: ", result)

# Executa a calculadora
calculate()
