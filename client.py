from socket import *
import json

server_name = 'localhost'
server_port = 12000
BUFFER_SIZE = 1024
client_socket = socket(AF_INET, SOCK_STREAM)

client_socket.connect((server_name, server_port))

user_id = input("Enter your name: ")
port = int(input("Enter port number: "))

user_info = {
    "id": user_id,
    "port": port
}
body_text = json.dumps(user_info)

header = (
    "POST /login HTTP/1.0\r\n"
	"Content-Type: application/json\r\n"
	f"Content-Length: {len(body_text)}\r\n"
	"\r\n"
)

header_bytes = header.encode()
body_bytes = body_text.encode()

packet = header_bytes + body_bytes

client_socket.send(packet)

response = client_socket.recv(BUFFER_SIZE)
print('From Server:', response.decode())

client_socket.close()
