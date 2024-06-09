def main():
    print("Calculadora básica")
    print("Operações suportadas: +, -, *, /, %\n")
    
    while True:
        expression = input("Entre com a expressão: ")
        
        if expression == 'quit':
            break
        
        try:
            result = eval(expression)
            print("Resultado:", result)
        except:
            print("Expressão inválida. Tente novamente.")

if __name__ == '__main__':
    main()
