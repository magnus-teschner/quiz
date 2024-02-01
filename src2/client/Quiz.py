import sys
import os
import uuid
import ast
from time import sleep
import threading
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from middleware.middleware import Middleware

from Player import PlayersList
import json


states = {}
class Statemachine():
    UUID = str(uuid.uuid4())
    gameRoomPort = 61424
    currentState = ''

    class State:
        total_States = 0
        def __init__(self, name):
            self.name = name
            self.id = self.total_States
            self.total_States += 1
            states[name] = self

        def run(self):
            pass

    @classmethod
    def switchToState(cls, targetState):
        if "exit" in dir(states[cls.currentState]):
            states[cls.currentState].exit()

        if "entry" in dir(states[targetState]):
            states[targetState].entry()
        cls.currentState = targetState

    def __init__(self):
        self.players = PlayersList()
        self.question_answer = ""
        self.commited_answers = 0
        Statemachine.UUID = str(uuid.uuid4())
        self.middleware = Middleware(Statemachine.UUID, self)
        Statemachine.currentState = "Initializing"
        tempState = self.State("Initializing")

        def state_initializing():
            print(f"UUID: {self.middleware.MY_UUID}")
            self.playerName = input("Select your Player Name: ")
            gamePort = input("Select Game Room Port (Leave Empty for default value of 61424) : ")
            self.gameRoomPort = (int(gamePort) if gamePort else 61424)
            self.players.addPlayer(self.middleware.MY_UUID, self.playerName)

            if True:
                self.switchToState("Lobby")
        tempState.run = state_initializing

        tempState = self.State("Lobby")
        def Lobby_entry():
            self.middleware.leaderUUID = self.middleware.MY_UUID
            print(f"This is leader UUID: {self.middleware.leaderUUID}")
            self.middleware.subscribeBroadcastListener(self.respondWithPlayerList)
            self.middleware.subscribeTCPUnicastListener(self.listenForPlayersList)
            command = "enterLobby"
            data = self.playerName
            print("\nSent Broadcast!")
            self.middleware.broadcastToAll(command, data)
        tempState.entry = Lobby_entry

        def lobby_waiting():
            sleep(0.5)
            print("")
            print(self.middleware.leaderUUID)
            print("")
            print("")
            if self.middleware.leaderUUID == self.middleware.MY_UUID:
                print("I am leader")
                self.switchToState("wait_for_peers")
            else:
                self.switchToState("wait_for_start")
        tempState.run = lobby_waiting

        #States specific to the leader of the Quiz Game
        tempState = self.State("wait_for_peers")
        def wait_for_peers_entry():
            if len(self.players.playerList) < 3:
                print("Waiting for more players - 3 players needed at minimum!")
        tempState.entry = wait_for_peers_entry

        def wait_for_peers():
            if len(self.players.playerList) >= 3:
                self.switchToState("start_new_round")
        tempState.run = wait_for_peers

        tempState = self.State("start_new_round")
        def start_new_round():
            print_lock = threading.Lock()
            with print_lock:
                self.question = input("\n What is your question? \n")
                self.answer_a = input("Enter answer possibility a: ")
                self.answer_b = input("Enter answer possibility b: ")
                self.answer_c = input("Enter answer possibility c: ")
                self.correct_answer = input("Enter letter of correct answer (e.G a or b or c): ")
            self.question_answer = [self.question,self.answer_a, self.answer_b, self.answer_c, self.correct_answer]
            self.middleware.multicastReliable('startNewRound', str(self.question_answer))
            print(f'Multicasted question and answers: {str(self.question_answer)}')
            self.switchToState("wait_for_responses")
        tempState.run = start_new_round

        tempState = self.State("wait_for_responses")
        def wait_for_responses_entry():
            self.middleware.subscribeTCPUnicastListener(self.collectInput)
        tempState.entry = wait_for_responses_entry

        def wait_for_response():
            """
            if self.receiver_counter == len(self.players.playerList) -1:
                self.switchToState("Lobby")
            self.middleware.multicastReliable('toLobby', "placeholder")
            """
        tempState.run = wait_for_response

        def wait_for_response_exit():
            self.middleware.unSubscribeTCPUnicastListener(self.collectInput)
        tempState.exit = wait_for_response_exit

        # #States specific to the players which are not leaders
        tempState = self.State("wait_for_start")
        def wait_for_start_entry():
            self.middleware.subscribeTCPUnicastListener(self.onReceiveNewRound)
            self.middleware.subscribeTCPUnicastListener(self.collectInput)
        tempState.entry = wait_for_start_entry

        def wait_for_start():
            if self.question_answer != '':
                self.switchToState("play_game")
            elif self.middleware.leaderUUID == Middleware.MY_UUID:
                self.switchToState("wait_for_peers")
        tempState.run = wait_for_start

        tempState = self.State("play_game")
        def play_game():
            print(f"Question: {self.question_answer[0]}")
            print(f"       a) {self.question_answer[1]}")
            print(f"       b) {self.question_answer[2]}")
            print(f"       c) {self.question_answer[3]}")
            answer = input("Enter your answer: ")
            self.middleware.multicastReliable("playerResponse", answer)
            if answer == self.question_answer[4]:
                self.players.addPoints(self.middleware.MY_UUID, 10)
                self.players.printLobby()
            self.switchToState("player_wait_for_all_answers")
        tempState.run = play_game

        def play_game_exit():
            self.middleware.unSubscribeTCPUnicastListener(self.onReceiveNewRound)
            self.middleware.unSubscribeTCPUnicastListener(self.collectInput)
            
        tempState = self.State("player_wait_for_all_answers")
        def player_wait_for_all_answers_entry():
            self.middleware.subscribeTCPUnicastListener(self.collectInput)
        tempState.entry = player_wait_for_all_answers_entry

        def player_wait_for_all_answers():
            pass    
        tempState.run = player_wait_for_all_answers
        def player_wait_for_all_answers_exit():
            self.middleware.unSubscribeTCPUnicastListener(self.collectInput)
            self.question_answer = ""
        tempState.exit = player_wait_for_all_answers_exit


    def listenForPlayersList(self, messengerUUID:str, messengerSocket, command:str, playersList:str):
        if command == 'PlayerList':
            self.middleware.leaderUUID = messengerUUID
            self.players.updateList(playersList)

    def respondWithPlayerList(self, messengerUUID:str, command:str, playerName:str):
        if command == 'enterLobby':
            print(messengerUUID)
            self.players.addPlayer(messengerUUID, playerName)
            if self.middleware.MY_UUID == self.middleware.leaderUUID:
                print("only I am the leader")
                self.middleware.sendIPAdressesto(messengerUUID)
                responseCommand = 'PlayerList'
                responseData = self.players.toString()
                self.middleware.sendTcpMessageTo(messengerUUID, responseCommand, responseData)

    def onReceiveNewRound(self, messengerUUID, clientsocket, messageCommand, messageData):
            if messageCommand == "startNewRound":
                self.question_answer = ast.literal_eval(messageData)

    def collectInput(self, messengerUUID, clientsocket, messageCommand, messageData):
        if messageCommand == 'playerResponse':
            print("received_input")
            self.commited_answers += 1
            print(self.commited_answers)
            if messageData == self.question_answer[-1]:
                print("add_points")
                self.players.addPoints(messengerUUID, 10)
                self.players.printLobby()

            if self.middleware.leaderUUID == self.middleware.MY_UUID and self.commited_answers == (len(self.players.playerList) -1):
                self.switchToState("start_new_round")

            elif self.commited_answers == (len(self.players.playerList) -2):
                self.switchToState("wait_for_start")
                
    def runLoop(self):
        states[self.currentState].run()


if __name__ == '__main__':
    print("Welcome to the peer to peer quiz game!")
    SM = Statemachine()
    while True:
        SM.runLoop()










