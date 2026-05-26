import select
import socket
from socket import *
import json
import sys
from utils import parse_message, make_req_msg, make_res_msg

# global varibale
server_name = 'localhost'
server_port = 12000
BUFFER_SIZE = 1024

user_dict = {}
my_info = {}
active_rooms = {}

client_socket: socket | None = None

# login
def login() -> bytes:
    global user_dict, client_socket

    user_id = input("Enter your name: ")
    port = int(input("Enter port number: "))

    client_socket = socket(AF_INET, SOCK_STREAM)
    client_socket.connect((server_name, server_port))

    global my_info
    my_info = {
        "id": user_id,
        "port": port
    }

    body_text = json.dumps({
        user_id: {
            "port": port
        }
    })
    packet = make_req_msg("POST", "/login", body_text)

    client_socket.sendall(packet)

    response = client_socket.recv(BUFFER_SIZE)
    my_info["ip"] = client_socket.getsockname()[0]

    header, body = parse_message(response)
    user_dict = json.loads(body)

    # online인 users 출력
    print(f"{user_id} 님 로그인 성공했습니다.")
    print_user_dict()
    print("\n<Command>")
    print("1. quit\n2. msg <username> <msg>")

    return response


def print_user_dict():
    print()
    print("<Online Users>")

    cnt = 0
    for user in user_dict:
        if my_info.get("id") != user:
            cnt += 1
            print(f"{cnt}. {user}")

    if len(user_dict) <= 1:
        print("아무도 없나요???")


def update_user_dict():
    global user_dict, client_socket

    req_msg = make_req_msg("GET", "/users")
    client_socket.sendall(req_msg)

    response = client_socket.recv(BUFFER_SIZE)

    header, body = parse_message(response)

    if header.get("Status") == 200:
        user_dict = json.loads(body)


def chat():
    global my_info, client_socket, user_dict

    p2p_listen_sock = socket(AF_INET, SOCK_STREAM)
    p2p_listen_sock.bind((my_info["ip"], my_info["port"]))
    p2p_listen_sock.listen(5)

    read_list: list[socket] = [p2p_listen_sock, sys.stdin, client_socket]

    while True:
        r_ready, _, _ = select.select(read_list, [], [])

        sock: socket.socket
        for sock in r_ready:
            if sock == sys.stdin:
                command = sys.stdin.readline().strip()
                cmd = command.split(" ")

                # quit하면 모든 소켓을 다 닫고 return
                if cmd[0] == "quit":
                    for i in range(len(read_list)):
                        read_list[i].close()

                    return

                elif cmd[0] == "msg":
                    # 보낼 user 이름과 메세지 입력받기
                    target_name = cmd[1]

                    if target_name in user_dict:
                        target_info = user_dict.get(target_name)
                    else:
                        continue

                    # 연결한 적 없으면 socket 생성
                    if target_name in active_rooms:
                        target_sock = active_rooms[target_name]
                    else:
                        target_info = user_dict.get(target_name)
                        target_sock = socket(AF_INET, SOCK_STREAM)
                        target_sock.connect((target_info.get("ip"), target_info.get("port")))

                        active_rooms[target_name] = target_sock
                        read_list.append(target_sock)

                    message = ' '.join(cmd[2:])
                    msg = make_req_msg(
                        "SEND",
                        "/send",
                        message,
                        extra_field=[
                            ("From", my_info.get("id"))
                        ]
                    )

                    target_sock.sendall(msg)

            # handshake?
            elif sock == p2p_listen_sock:
                connection_sock, address = p2p_listen_sock.accept()
                read_list.append(connection_sock)

            # receive to server
            elif sock == client_socket:
                request = sock.recv(BUFFER_SIZE)
                header, body = parse_message(request)

                if header.get("Status-Message") == "OK":
                    user_dict = json.loads(body)
                    print_user_dict()
                    sock.sendall(make_res_msg(200))

                else:
                    sock.sendall(make_res_msg(400))

            # sent a message to the peer
            else:
                message = sock.recv(BUFFER_SIZE)

                if not message:
                    print("\n상대방과의 연결이 끊겼습니다.")
                    read_list.remove(sock)
                    for name, act_sock in active_rooms.items():
                        if act_sock == sock:
                            del active_rooms[name]
                            break
                    continue

                header, body = parse_message(message)

                # receive chat
                if "Method" in header:
                    print(f"{header.get("From")}: {body}")
                    sock.send(make_res_msg(200))


def main():
    global user_dict

    header, body = parse_message(login())
    if header.get("status") == 200:
        print("Success login")

    chat()

if __name__ == "__main__":
    main()