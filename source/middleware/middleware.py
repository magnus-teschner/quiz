import uuid
import threading
import socket
import ipaddress
from time import sleep
from dataclasses import dataclass



######################################### PARAMETER Constants
BROADCAST_PORT = 61424
BUFFER_SIZE = 1024
SUBNETMASK = "255.255.255.0"

IP_ADRESS_OF_THIS_PC = socket.gethostbyname(socket.gethostname())
net = ipaddress.IPv4Network(IP_ADRESS_OF_THIS_PC + '/' + SUBNETMASK, False)
BROADCAST_IP = net.broadcast_address.exploded

class Middleware():
    ipAdresses = {} # {uuid: (ipadress, port)} (str , int)
    MY_UUID = ''
    neighborUUID = None
    neighborAlive = False
    
    def __init__(self,UUID, statemashine):
        Middleware.MY_UUID = UUID 
        self.statemashine =  statemashine
        self._broadcastHandler = BroadcastHandler()
        self._unicastHandler = UDPUnicastHandler()
        self._tcpUnicastHandler = TCPUnicastHandler()
        self.subscribeTCPUnicastListener(self._updateAdresses)
        self.subscribeTCPUnicastListener(self._checkForVotingAnnouncement)

        self.sendHB = threading.Thread(target=self._sendHeartbeats)
        self.sendHB.start()
        Middleware.neighborAlive = False
        self.subscribeUnicastListener(self._listenHeartbeats)
        self.subscribeTCPUnicastListener(self._listenLostPlayer)

        self.leaderUUID = ''

    def findNeighbor(self, ownUUID, ipaddresses):
        ordered = sorted(ipaddresses.keys())
        if ownUUID in ordered:
            ownIndex = ordered.index(ownUUID)

            uuidList = list(ordered)
            if uuidList[ownIndex - 1] != ownUUID:
                return uuidList[ownIndex - 1]

    def _sendHeartbeats(self):
        ctr = 0
        while True:
            Middleware.neighborAlive = False
            if not Middleware.neighborUUID:
                Middleware.neighborUUID = self.findNeighbor(Middleware.MY_UUID, Middleware.ipAdresses)
                sleep(1)
            else:
                self.sendMessageTo(Middleware.neighborUUID, 'hbping', Middleware.MY_UUID)
                sleep(1)
                if ctr < 3 and not Middleware.neighborAlive:
                    ctr += 1
                elif not Middleware.neighborAlive and ctr >= 3:
                    ctr = 0
                    Middleware.ipAdresses.pop(Middleware.neighborUUID, None)
                    self.statemashine.players.removePlayer(Middleware.neighborUUID)
                    self.multicastReliable('lostplayer', Middleware.neighborUUID)
                    if Middleware.neighborUUID == self.leaderUUID:
                        self.initiateVoting()
                    Middleware.neighborUUID = None
                elif Middleware.neighborAlive:
                    ctr = 0
                else:
                    Middleware.neighborUUID = None
                    ctr = 0

    def _listenHeartbeats(self, messengeruuid:str, command:str, data:str):
        if command == 'hbping':
            self.sendMessageTo(messengeruuid, 'hbresponse', Middleware.MY_UUID)
        elif command == 'hbresponse':
            if messengeruuid == Middleware.neighborUUID:
                Middleware.neighborAlive = True

    def _listenLostPlayer(self, messengerUUID:str, clientsocket:socket.socket, command:str, data:str):
        if command == 'lostplayer':           
            Middleware.ipAdresses.pop(data, None)            
            Middleware.neighborUUID = None
            self.statemashine.players.removePlayer(data)
    

    @classmethod
    def addIpAdress(cls, uuid, addr):
        cls.ipAdresses[uuid] = addr
        Middleware.neighborUUID = None

    def broadcastToAll(self, command:str, data:str=''):
        self._broadcastHandler.broadcast(command+':'+data)
    
    def sendMessageTo(self, uuid:str, command:str, data:str=''): # unicast
        ipAdress = Middleware.ipAdresses[uuid]
        self._unicastHandler.sendMessage(ipAdress, command+':'+data)
    
    def sendTcpMessageTo(self, uuid:str, command:str, data:str=''):
        addr = Middleware.ipAdresses[uuid]
        self._tcpUnicastHandler.sendMessage(addr, command+':'+data)
    
    def sendTcpRequestTo(self, uuid:str, command:str, data:str=''):
        addr = Middleware.ipAdresses[uuid] 
        return self._tcpUnicastHandler.sendTcpRequestTo(addr, command+':'+data) 

    def multicastReliable(self, command:str, data:str=''):
        message = command+':'+data
        for key, addr in Middleware.ipAdresses.items():
            if key != Middleware.MY_UUID:
                self._tcpUnicastHandler.sendMessage(addr, message)

    def sendIPAdressesto(self,uuid):
        command='updateIpAdresses'
        s=self.leaderUUID + '$'
        for uuid, (addr,port) in Middleware.ipAdresses.items():
            s +=  uuid+','+str(addr)+','+str(port)+'#'
        self.sendTcpMessageTo(uuid,command,s)

    def subscribeBroadcastListener(self, observer_func):
        """observer_func gets called every time there this programm recieves a broadcast message

        Args:
            observer_func ([type]): observer_function needs to have func(self, messengerUUID:str, command:str, data:str)
        """
        self._broadcastHandler.subscribeBroadcastListener(observer_func)
    def subscribeUnicastListener(self, observer_func):
        """observer_func gets called every time this programm recieves a Unicast message

        Args:
            observer_func ([type]): observer_function needs to have func(self, messengerUUID:str, command:str, data:str)
        """
        self._unicastHandler.subscribeUnicastListener(observer_func)
    def subscribeTCPUnicastListener(self, observer_func):
        """observer_func gets called every time this programm recieves a Unicast message
        Args:
            observer_func ([type]): observer_function needs to have observer_func(self, messengerUUID:str, clientsocket:socket.socket, command:str, data:str) 
        """
        self._tcpUnicastHandler.subscribeTCPUnicastListener(observer_func)
    
    def unSubscribeTCPUnicastListener(self, rmFunc):
        self._tcpUnicastHandler.unSubscribeTCPUnicastListener(rmFunc)
            
    def _updateAdresses(self, messengerUUID:str, clientsocket, command:str, data:str):
        """_updateAdresses recieves and decodes the IPAdresses List from the function 
        sendIPAdressesto(self,uuid)

        Args:
            command (str): if this argument NOT == 'updateIpAdresses' this function returns without doing anything
            message (str): list of uuid's and IPAdresses
        """
        if command == 'updateIpAdresses':
            data = data.split('$')
            self.leaderUUID = data[0]
            secondArgument = data[1]
            removedLastHashtag = secondArgument[0:-1]
            for addr in removedLastHashtag.split('#'):
                addrlist = addr.split(',')
                self.addIpAdress(addrlist[0], (addrlist[1], int(addrlist[2])))

    def _checkForVotingAnnouncement(self, messengerUUID:str, clientsocket:socket.socket, command:str, data:str):
        if command == 'voting':
            if data == Middleware.MY_UUID:
                print('\nI am the new Game-Master\n')
                self.multicastReliable('leaderElected', Middleware.MY_UUID)
                self.leaderUUID = Middleware.MY_UUID
                self.statemashine.switchToState("start_new_round")
            elif data < Middleware.MY_UUID:
                # send my UUID to neighbour
                command = 'voting'
                data = Middleware.MY_UUID
                #print('\nsend voting command with my UUID (' + Middleware.MY_UUID + ') to lowerNeighbour')
                self.sendTcpMessageTo(self.findLowerNeighbour(), command, data)
                
            # if greater UUID
            elif data > Middleware.MY_UUID:
                # send received UUID to neighbour
                command = 'voting'
                print('\nsend voting command with recevied UUID (' + data + ') to lowerNeighbour\n')
                self.sendTcpMessageTo(self.findLowerNeighbour(), command, data)
        elif command == 'leaderElected':
            print('new Leader got elected\n')
            self.leaderUUID = data
            self.answered = False
            self.question_answer = ''
            self.commited_answers = 0
            self.statemashine.switchToState("wait_for_start")

    # diese Funktion muss aufgerufen werden um ein neues Voting zu starten
    def initiateVoting(self):
        # send to lowerNeighbour: voting with my UUID
        command = 'voting'
        data = Middleware.MY_UUID
        #print('Initiate new Voting!\n')
        #print('\nsend voting command with my UUID (' + Middleware.MY_UUID + ') to lowerNeighbour')
        self.sendTcpMessageTo(self.findLowerNeighbour(), command, data)

    def findLowerNeighbour(self):
        ordered = sorted(self.ipAdresses.keys())
        ownIndex = ordered.index(Middleware.MY_UUID)

        neighbourUUID = ordered[ownIndex - 1]
        assert Middleware.MY_UUID != neighbourUUID, 'I am my own neigbour that shouldnt happen'
        #print('Neighbour: ' + neighbourUUID)
        return neighbourUUID
        # send to next higher node we start a voting with my UUID

class UDPUnicastHandler():
    _serverPort = 0 # later changed in the init, it is here to define it as a class variable, so that it is accessable easyly 

    def __init__(self):
        # Create a UDP socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # AF_INET means that this socket Internet Protocol v4 addresses
                                                            #SOCK_DGRAM means this is a UDP scoket
        self._server_socket.bind(('', 0)) # ('', 0) '' use the lokal IP adress and 0 select a random open port
        UDPUnicastHandler._serverPort = self._server_socket.getsockname()[1] # returns the previously selected (random) port
        #print("ServerPort = ",UDPUnicastHandler._serverPort)
        self.incommingUnicastHistory = []
        self._listenerList = [] # observer pattern

        # Create Thread to listen to UDP unicast
        self._listen_UDP_Unicast_Thread = threading.Thread(target=self._listenUnicast)
        self._listen_UDP_Unicast_Thread.start()

    
    def sendMessage(self, addr, message:str):
        self._server_socket.sendto(str.encode(Middleware.MY_UUID + '_'+IP_ADRESS_OF_THIS_PC + '_'+str(UDPUnicastHandler._serverPort)+'_'+message), addr)
        #print('UnicastHandler: sent message: ', message,"\n\tto: ", addr)

    def _listenUnicast(self):
        #print("listenUDP Unicast Thread has started and not blocked Progress (by running in the background)")
        while True:
            try:
                data, address = self._server_socket.recvfrom(BUFFER_SIZE)
                data = data.decode('utf-8')
                #print('UnicastHandler: Received message from client: ', address)
                #print('\t\tMessage: ', data)

                if data:
                    data=data.split('_')
                    messengerUUID = data[0]
                    messengerIP = data[1]
                    messengerPort = int(data[2])    # this should be the port where the unicast listener socket 
                                                    #(of the sender of this message) is listening on
                    assert address ==  (messengerIP, messengerPort)                              
                    message=data[3]
                    messageSplit= message.split(':')
                    assert len(messageSplit) == 2, "There should not be a ':' in the message"
                    messageCommand = messageSplit[0]
                    messageData = messageSplit[1]

                    self.incommingUnicastHistory.append((message, address))
                    for observer_func in self._listenerList:
                        observer_func(messengerUUID, messageCommand, messageData) 
                    data[1] = None
            except:
                #print("Connection was lost!")
                pass

    def subscribeUnicastListener(self, observer_func):
        self._listenerList.append(observer_func)

class TCPUnicastHandler():
    # this class needs to be initiated after the unicast Handler
    def __init__(self):
        # Create a TCP socket for listening
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # AF_INET means that this socket Internet Protocol v4 addresses
                                                            #SOCK_STREAM means this is a TCP scoket
        self._server_socket.bind(('', UDPUnicastHandler._serverPort)) # ('', ) '' use the lokal IP adress and 0 select the same port as the udpUnicastHandler. you can use both protocols on the same port

        self.incommingUnicastHistory = []
        self._listenerList = [] # observer pattern

        # Create Thread to listen to TCP unicast
        self._listen_UDP_Unicast_Thread = threading.Thread(target=self._listenTCPUnicast)
        self._listen_UDP_Unicast_Thread.start()

    
    def sendMessage(self, addr: tuple, message:str): # open new connection; send message and close immediately
        threading.Thread(target = self._sendMessageThread, args = (addr,message)).start()

    def _sendMessageThread(self, addr: tuple, message:str):
        sendSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # AF_INET means that this socket Internet Protocol v4 addresses
        sendSocket.bind(('', 0))

        try:
            sendSocket.connect(addr)
            messageBytes = str.encode(Middleware.MY_UUID + '_'+IP_ADRESS_OF_THIS_PC + '_'+str(UDPUnicastHandler._serverPort)+'_'+message)
            sendSocket.send(messageBytes)
        except ConnectionRefusedError:
            pass
        finally:
            sendSocket.close() # Further sends are disallowed
        
        
    def sendTcpRequestTo(self, addr:tuple, message:str):
        # this is blocking
        sendSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # AF_INET means that this socket Internet Protocol v4 addresses
        sendSocket.bind(('', 0))
        response = None
        try:
            sendSocket.connect(addr)
            messageBytes = str.encode(Middleware.MY_UUID + '_'+IP_ADRESS_OF_THIS_PC + '_'+str(UDPUnicastHandler._serverPort)+'_'+message)
            sendSocket.send(messageBytes)
            response = sendSocket.recv(BUFFER_SIZE).decode('utf-8')
        except ConnectionRefusedError:
            print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  ERROR')
            print('Process on address ', addr, 'is not connecting')
        finally:
            sendSocket.close() # close this socket
        return response



    def _listenTCPUnicast(self):
        self._server_socket.listen(5)

        while True:
            clientsocket, address = self._server_socket.accept()
            clientsocket.settimeout(60)
            threading.Thread(target = self._listenToClient, args = (clientsocket,address)).start()


    def _listenToClient(self, clientsocket:socket.socket, address):
        data = clientsocket.recv(BUFFER_SIZE)
        data = data.decode('utf-8')

        if data:
            data=data.split('_')
            messengerUUID = data[0]
            messengerIP = data[1]
            messengerPort = int(data[2])
                             
            message=data[3]
            messageSplit= message.split(':')
            assert len(messageSplit) == 2, "There should not be a ':' in the message"
            messageCommand = messageSplit[0]
            messageData = messageSplit[1]
            self.incommingUnicastHistory.append((message, address))
            for observer_func in self._listenerList:
                observer_func(messengerUUID, clientsocket, messageCommand, messageData)
        clientsocket.close()

    def subscribeTCPUnicastListener(self, observer_func):
        self._listenerList.append(observer_func)
        
    def unSubscribeTCPUnicastListener(self, rmFunc):
        self._listenerList = [x for x in self._listenerList if x != rmFunc]
class BroadcastHandler():
    def __init__(self):
        self.incommingBroadcastHistory = []
        self._listenerList = []

        self._broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Create a UDP socket for Listening
        self._listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set the socket to broadcast and enable reusing addresses
        self._listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind socket to address and port
        self._listen_socket.bind((IP_ADRESS_OF_THIS_PC, BROADCAST_PORT))

        # Create Thread to listen to UDP Broadcast
        self._listen_UDP_Broadcast_Thread = threading.Thread(target=self._listenUdpBroadcast)
        self._listen_UDP_Broadcast_Thread.start()

    def broadcast(self, broadcast_message:str):
        """Send message to the broadcast Port defined at lauch of the Programm

        Args:
            broadcast_message (str): needs to have the format  "command:data" (the data could be csv encode with , and #)
        """
        # Send message on broadcast address
        self._broadcast_socket.sendto(str.encode(Middleware.MY_UUID + '_'+IP_ADRESS_OF_THIS_PC + '_'+str(UDPUnicastHandler._serverPort)+'_'+broadcast_message, encoding='utf-8'), (BROADCAST_IP, BROADCAST_PORT))
        #                                                                                                                  ^this is the port where the _listen_UDP_Unicast_Thread ist listening on
        #self.broadcast_socket.close()

    def subscribeBroadcastListener(self, observer_func):
        self._listenerList.append(observer_func)
    def _listenUdpBroadcast(self):
        #print("listenUDP Broadcast Thread has started and not blocked Progress (by running in the background)")
        while True:
            # Code waits here until it recieves a unicast to its port
            # thats why this code needs to run in a different thread
            data, addr = self._listen_socket.recvfrom(BUFFER_SIZE)
            data = data.decode('utf-8')
            if data:
                data=data.split('_')
                messengerUUID = data[0]
                messengerIP = data[1]
                messengerPort = int(data[2])    # this should be the port where the unicast listener socket 
                                                #(of the sender of this message) is listening on
                message=data[3]
                Middleware.addIpAdress(messengerUUID,(messengerIP, messengerPort)) # add this to list override if already present
                if messengerUUID != Middleware.MY_UUID:
                    #print("Received broadcast message form",addr, ": ", message)
                    message=data[3]
                    messageSplit= message.split(':')
                    assert len(messageSplit) == 2, "There should not be a ':' in the message"
                    messageCommand = messageSplit[0]
                    messageData = messageSplit[1]
                    self.incommingBroadcastHistory.append((messengerUUID, message))
                    for observer_func in self._listenerList:
                        observer_func(messengerUUID, messageCommand, messageData)
                data = None