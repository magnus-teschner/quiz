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

        if "entry" in dir(states[cls.currentState]):
            states[cls.currentState].entry()

        cls.currentState = targetState

    def __init__(self):
        self.middleware = Middleware(Statemachine.UUID, self)
        Statemachine.currentState = "Initializing"
        tempState = self.State("Initializing")
        def state_initializing():
            print(f"UUID: {Middleware.MY_UUID}")
            self.playerName = input("Select your Player Name: ")
            gamePort = input("Select Game Room Port: \nLeave Empty for default value of 60000")
            self.gameRoomPort = (int(gamePort) if gamePort else 60000)

        tempState.run = state_initializing

    def runLoop(self):
        states[self.currentState].run()



if __name__ == 'main':
    print("Peer to peer quiz game")
    SM = Statemachine()
    while True:
        SM.runLoop()
        sleep(1/1000000)









