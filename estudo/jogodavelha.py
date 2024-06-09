import os
import random

def display_board(board):
    print(f' {board[0]} | {board[1]} | {board[2]} ')
    print('---+---+---')
    print(f' {board[3]} | {board[4]} | {board[5]} ')
    print('---+---+---')
    print(f' {board[6]} | {board[7]} | {board[8]} ')

def select_char():
    char = ""
    while char != 'X' and char != 'O':
        char = input("Escolha 'X' ou 'O': ").upper()

    if char == 'X':
        return ('X', 'O')
    else:
        return ('O', 'X')

def place_char(board, char, pos):
    board[pos] = char

def win_check(board, char):
    return ((board[0] == char and board[1] == char and board[2] == char) or
    (board[3] == char and board[4] == char and board[5] == char) or
    (board[6] == char and board[7] == char and board[8] == char) or
    (board[0] == char and board[3] == char and board[6] == char) or
    (board[1] == char and board[4] == char and board[7] == char) or
    (board[2] == char and board[5] == char and board[8] == char) or
    (board[0] == char and board[4] == char and board[8] == char) or
    (board[2] == char and board[4] == char and board[6] == char))

def space_check(board, pos):
    return board[pos] == ' '

def full_board_check(board):
    return ' ' not in board

def player_choice(board, char):
    pos = int(input(f"Escolha uma posição de 1 a 9 para colocar sua {char}: ")) - 1
    if space_check(board, pos):
        place_char(board, char, pos)
    else:
        print("Posição já ocupada. Escolha outra posição.")
        player_choice(board, char)

def choose_first():
    return random.choice(['player1', 'player2'])

def play_game():
    os.system('clear')
    board = [' '] * 9
    player1_char, player2_char = select_char()
    turn = choose_first()
    game_on = True

    while game_on:
        if turn == 'player1':
            display_board(board)
            print("\033[1mJogador 1:\033[0m")
            player_choice(board, player1_char)
            if win_check(board, player1_char):
                display_board(board)
                print("Parabéns, jogador 1 ganhou!")
                game_on = False
            else:
                if full_board_check(board):
                    display_board(board)
                    print("Empate!")
                    game_on = False
                else:
                    turn = 'player2'

        else:
            display_board(board)
            print("\033[1mJogador 2:\033[0m")
            player_choice(board, player2_char)
            if win_check(board, player2_char):
                display_board(board)
                print("Parabéns, jogador 2 ganhou!")
                game_on = False
            else:
                if full_board_check(board):
                    display_board(board)
                    print("Empate!")
                    game_on = False
                else:
                    turn = 'player1'

play_game()

