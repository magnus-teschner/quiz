import sys
import os
import uuid
from time import sleep
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 
from middleware.middleware import Middleware
import time
from Player import PlayersList

import msvcrt

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
            #self.middleware.subscribeTCPUnicastListener(self.listenForPlayersList)

            command = "enterLobby"
            data = self.playerName
            self.middleware.broadcastToAll(command, data)
            print("send broadcast")

        tempState.entry = Lobby_entry


    def listenForPlayersList(self, messengerUUID:str, messengerSocket, command:str, playersList:str):
        if command == 'PlayerList':
            self.middleware.leaderUUID = messengerUUID
            self.players.updateList(playersList)

    def respondWithPlayerList(self, messengerUUID:str, command:str, playerName:str):
        if command == 'enterLobby':
            self.players.addPlayer(messengerUUID, playerName)
            if Middleware.MY_UUID == self.middleware.leaderUUID:
                self.middleware.sendIPAdressesto(messengerUUID)
                responseCommand = 'PlayerList'
                responseData = self.players.toString()
                self.middleware.sendTcpMessageTo(messengerUUID, responseCommand, responseData)

    def runLoop(self):
        states[self.currentState].run()



if __name__ == '__main__':
    print("Peer to peer quiz game")
    SM = Statemachine()
    while True:
        SM.runLoop()
        sleep(1/1000000)









