import socket
import threading
import time
import uuid

class QuizGameHost:
    def __init__(self, port=0):
        self.guid = str(uuid.uuid4())
        self.port = port
        self.peers = {}  # Dictionary to store peer addresses and their GUIDs
        self.leader = None
        self.sequence_number = 0

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('', self.port))
        self.server_socket.listen()
        print(f"Listening on {self.server_socket.getsockname()}")
        threading.Thread(target=self.accept_connections, daemon=True).start()

    def accept_connections(self):
        while True:
            client_socket, address = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(client_socket, address), daemon=True).start()

    def handle_client(self, client_socket, address):
        received_data = client_socket.recv(1024).decode('utf-8')
        # Basic command handling (join, heartbeat, etc.)
        print(f"Received data from {address}: {received_data}")
        # Example: handle join request
        if received_data == 'join':
            self.peers[address] = received_data  # Store peer information
            client_socket.send(self.guid.encode('utf-8'))
        client_socket.close()

    def send_heartbeat(self, peer_address):
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect(peer_address)
                    s.sendall(b'heartbeat')
                    time.sleep(2)  # Send heartbeat every 2 seconds
            except ConnectionError:
                print(f"Failed to send heartbeat to {peer_address}")
                break

    def multicast_message(self, message):
        for peer_address in self.peers.keys():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect(peer_address)
                    s.sendall(f"{self.sequence_number}:{message}".encode('utf-8'))
            except Exception as e:
                print(f"Error sending message to {peer_address}: {e}")
        self.sequence_number += 1

    def vote_for_leader(self):
        # Simplified voting mechanism: votes for itself
        self.leader = self.guid
        for peer in self.peers:
            self.send_vote(peer, self.guid)

    def send_vote(self, peer_address, vote):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(peer_address)
                s.sendall(f"vote:{vote}".encode('utf-8'))
        except Exception as e:
            print(f"Error sending vote to {peer_address}: {e}")

# Example usage
if __name__ == "__main__":
    host = QuizGameHost()
    host.start_server()
    # Add more logic here for interaction, e.g., sending join requests to other hosts, starting heartbeats, etc.
