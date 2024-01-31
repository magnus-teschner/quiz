import sys
import os
import uuid
from time import sleep
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from middleware.middleware import Middleware

from Player import PlayersList
import json


states = {}
class Statemachine():
    UUID = str(uuid.uuid4())
    players = PlayersList()
    playerName = ''
    gameRoomPort = 61424
    currentState = ''
    question = ''
    answers = []

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
        Statemachine.UUID = str(uuid.uuid4())
        print(Statemachine.UUID, " and ", self  )
        self.question_answer = ''
       
        self.middleware = Middleware(Statemachine.UUID, self)
        Statemachine.currentState = "Initializing"
        tempState = self.State("Initializing")

        def state_initializing():
            print(f"UUID: {Middleware.MY_UUID}")
            self.playerName = input("Select your Player Name: ")
            gamePort = input("Select Game Room Port (Leave Empty for default value of 61424) : ")
            self.gameRoomPort = (int(gamePort) if gamePort else 61424)
            self.players.addPlayer(Middleware.MY_UUID, self.playerName)

            if True:
                self.switchToState("Lobby")
        tempState.run = state_initializing
        tempState = self.State("Lobby")

        def Lobby_entry():
            self.middleware.leaderUUID = Middleware.MY_UUID
            self.middleware.subscribeBroadcastListener(self.respondWithPlayerList)
            self.middleware.subscribeTCPUnicastListener(self.listenForPlayersList)

            command = "enterLobby"
            data = self.playerName
            self.middleware.broadcastToAll(command, data)
            print("send broadcast")

        tempState.entry = Lobby_entry

        def lobby_waiting():
            sleep(0.5)
            if self.middleware.leaderUUID == self.middleware.MY_UUID:
                self.switchToState("wait_for_peers")
            else:
                self.switchToState("wait_for_start")

        tempState.run = lobby_waiting

        # Leader states

        tempState = self.State("wait_for_peers")

        def wait_for_peers_entry():
            if len(self.players.playerList) < 3:
                print("Wait for players - 3 players needed at minimum")
        tempState.entry = wait_for_peers_entry

        def wait_for_peers():
            if len(self.players.playerList) >= 3:
                self.switchToState("start_new_round")

        tempState.run = wait_for_peers

        tempState = self.State("start_new_round")

        def start_new_round():
            self.question = input("What is your question?")
            self.answer_a = input("Enter answer possibility a: ")
            self.answer_b = input("Enter answer possibility b: ")
            self.answer_c = input("Enter answer possibility b: ")
            self.correct_answer = input("Enter letter of correct answer (e.G a or b or c): ")
            self.question_answer = {"question": self.question,"a": self.answer_a, "b": self.answer_b, "c": self.answer_c, "correct": self.correct_answer}
            self.multicastReliable('startNewRound', str(self.question_answer))
            print('Multicasted question and answers')
            self.switchToState("wait_for_responses")

        tempState.run = start_new_round

        tempState = self.State("wait_for_responses")
        def wait_for_responses_entry():
            pass #subscribe to multicast

        tempState.entry = wait_for_responses_entry

        def wait_for_response():
            pass #stays empty

        tempState.run = wait_for_response

        def wait_for_response_exit():
            pass #unsubscribe to multicast

        tempState.exit = wait_for_response_exit

        # Player states
        tempState = self.State("wait_for_start")
        def wait_for_start_entry():
            print("Waiting for game start")
            #Middleware.subscribeOrderedDeliveryQ(self.onReceiveNewRound)
            #Middleware.subscribeOrderedDeliveryQ(self.collectInput)

        tempState.entry = wait_for_start_entry

        def wait_for_start():
            if self.question_answer != '':
                self.switchToState("play_game")

            elif self.middleware.leaderUUID == Middleware.MY_UUID:
                Statemachine.switchStateTo("wait_for_peers")

        tempState.run = wait_for_start

        tempState = self.State("play_game")
        def play_game():
            print(f"Question: {self.question_answer["question"]}")
            print(f"""a): {self.question_answer["a"]} \n
           b): {self.question_answer["b"]} \n
           c): {self.question_answer["c"]} \n""")
            answer = input("Enter your answer: ")
            self.middleware.multicastReliable("playerResponse", answer)

        tempState.run = play_game

        def play_game_exit():
            #Middleware.unSubscribeOrderedDeliveryQ(self.onReceiveGameStart_f)
            #Middleware.subscribeOrderedDeliveryQ(self.collectPlayerInput_f)
            pass 

        tempState.exit = play_game_exit


    def listenForPlayersList(self, messengerUUID:str, messengerSocket, command:str, playersList:str):
        if command == 'PlayerList':
            self.middleware.leaderUUID = messengerUUID
            self.players.updateList(playersList)

    def respondWithPlayerList(self, messengerUUID:str, command:str, playerName:str):
        if command == 'enterLobby':
            print(messengerUUID)
            self.players.addPlayer(messengerUUID, playerName)
            if Middleware.MY_UUID == self.middleware.leaderUUID:
                self.middleware.sendIPAdressesto(messengerUUID)
                responseCommand = 'PlayerList'
                responseData = self.players.toString()
                print(responseData)
                self.middleware.sendTcpMessageTo(messengerUUID, responseCommand, responseData)

    def onReceiveNewRound(self, command, data):
        if command == "startNewRound":
            self.answer = json.loads(data)

    def collectInput(self, messengerUUID, command, data):
        if command == 'playerResponse':
            if data == self.question_answer["correct_answer"]:
                self.players.addPoints(messengerUUID, 10)
                self.question_answer = {}
                self.players.printLobby()
    

    def runLoop(self):
        states[self.currentState].run()


if __name__ == '__main__':
    print("Peer to peer quiz game")
    SM = Statemachine()
    while True:
        SM.runLoop()
        sleep(1/1000000)
        print(f"State Machine Player List: {SM.players.playerList}")









