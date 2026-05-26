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
read_list: list[socket] = []

client_socket: socket | None = None

# session variable
session_sockets: dict[str, socket] = {}
session_members: list[str] = []


def send_packet(sock: socket, method: str, url: str, body: str = "", extra_header: dict[str, str] | None = None):
    req_msg = make_req_msg(method, url, body, extra_header)
    sock.sendall(req_msg)


def receive_packet(sock: socket) -> tuple[dict, str]:
    try:
        raw_data = sock.recv(BUFFER_SIZE)
        if not raw_data:
            return {}, ""
        return parse_message(raw_data)
    except Exception as e:
        print(e)
        return {}, ""


# login
def login():
    global user_dict, client_socket, my_info

    user_id = input("Enter your name: ")
    port = int(input("Enter port number: "))

    client_socket = socket(AF_INET, SOCK_STREAM)
    client_socket.connect((server_name, server_port))

    my_info = {
        "id": user_id,
        "port": port
    }

    body_text = json.dumps({
        user_id: {
            "port": port
        }
    })

    send_packet(client_socket, "POST", "/login", body_text)

    my_info["ip"] = client_socket.getsockname()[0]


    header, body = receive_packet(client_socket)
    user_dict = json.loads(body)

    # online인 users 출력
    print(f"{user_id} 님 로그인 성공했습니다.")
    print_user_dict()
    print_commands()


def update_user_dict():
    global user_dict, client_socket

    send_packet(client_socket, "GET", "/users")

    header, body = receive_packet(client_socket)

    if header.get("Status") == 200:
        user_dict = json.loads(body)


def disconnect_client():
    for i in range(len(read_list)):
        read_list[i].close()
    exit()


def invite_user(target_name: str):
    # 없는 유저이거나 이미 세션에 있는 유저이면 return
    if target_name not in user_dict:
        print(f"{target_name} 님은 현재 오프라인이거나 없는 유저입니다.")
        return

    elif target_name in session_members:
        print(f"{target_name} 님은 이미 세션에 있습니다.")
        return

    # 연결한 적 없으면 socket 생성
    if target_name in session_sockets:
        target_sock = session_sockets[target_name]
    else:
        target_info = user_dict.get(target_name)
        target_sock = socket(AF_INET, SOCK_STREAM)
        target_sock.connect((target_info.get("ip"), target_info.get("port")))

        session_sockets[target_name] = target_sock
        read_list.append(target_sock)

    # 내 세션에 등록 및 select 감시 대상에 등록
    try:
        session_sockets[target_name] = target_sock
        session_members.append(target_name)

        send_packet(target_sock, "POST", "/invite", my_info.get("id"), {"From": my_info["id"]})

        print(f"{target_name} 님을 세션에 성공적으로 초대했습니다.")

    except Exception as e:
        print(f"세션 초대 실패: {e}")


def leave_session():
    print("현재 세션을 종료합니다.")

    for peer_sock in session_sockets.values():
        try:
            send_packet(peer_sock, "DELETE", "/leave", my_info.get("id"), {"From": my_info.get("id")})

            if peer_sock in read_list:
                read_list.remove(peer_sock)
            peer_sock.close()

        except Exception as e:
            print(e)

    # 세션 비우기
    session_sockets.clear()
    session_members.clear()


def send_message(target_name: str, message: str):
    if target_name in session_members:
        send_packet(
            session_sockets[target_name],
            "POST",
            "/send", message,
            extra_header={"From": my_info["id"]}
        )

    else:
        print(f"{target_name} 님은 현재 세션에 없습니다.")

def sendall_message(message: str):
    for mem in session_members:
        if mem != my_info.get("id"):
            send_message(mem, message)


def chat():
    global my_info, client_socket, user_dict, read_list

    p2p_listen_sock = socket(AF_INET, SOCK_STREAM)
    p2p_listen_sock.bind((my_info["ip"], my_info["port"]))
    p2p_listen_sock.listen(5)

    read_list = [p2p_listen_sock, sys.stdin, client_socket]

    while True:
        r_ready, _, _ = select.select(read_list, [], [])

        sock: socket.socket
        for sock in r_ready:
            # 사용자로부터 입력을 받았을 때
            if sock == sys.stdin:
                command = sys.stdin.readline().strip()
                cmd = command.split(" ")

                # quit하면 모든 소켓을 다 닫고 return
                if cmd[0] == "invite":
                    target_name = cmd[1]
                    invite_user(target_name)

                elif cmd[0] == "send":
                    target_name = cmd[1]
                    message = ' '.join(cmd[2:])
                    send_message(target_name, message)

                elif cmd[0] == "sendall":
                    message = ' '.join(cmd[1:])
                    sendall_message(message)

                elif cmd[0] == "leave":
                    leave_session()

                if cmd[0] == "quit":
                    disconnect_client()

            # handshake?
            elif sock == p2p_listen_sock:
                connection_sock, address = p2p_listen_sock.accept()
                read_list.append(connection_sock)

            # receive to server
            elif sock == client_socket:
                header, body = receive_packet(sock)

                if header.get("Status-Message") == "OK":
                    user_dict = json.loads(body)
                    print_user_dict()
                    sock.sendall(make_res_msg(200))

                else:
                    sock.sendall(make_res_msg(400))

            # sent a message to the peer
            else:
                header, body =  receive_packet(sock)

                if not header and not body:
                    print("\n상대방과의 연결이 끊겼습니다.")
                    read_list.remove(sock)
                    for name, act_sock in session_sockets.items():
                        if act_sock == sock:
                            del session_sockets[name]
                            break
                    continue

                # receive chat
                if "Method" in header:
                    method = header.get("Method")
                    url = header.get("URL")
                    sender_id = header.get("From")

                    # 상대방이 초대했을 때
                    if method == "POST" and url == "/invite":
                        if sender_id not in session_members:
                            session_members.append(sender_id)
                            session_sockets[sender_id] = sock

                        print(f"\n[세션 알림] {sender_id} 님의 메신저 세션에 초청되어 입장되었습니다! (현재 세션 멤버: {session_members})")
                        sock.sendall(make_res_msg(200))

                    # B. 상대방이 세션 전체에 메시지를 뿌린 경우
                    elif method == "POST" and url == "/send":
                        print(f"\n[{sender_id}]: {body}")
                        sock.sendall(make_res_msg(200))

                    # C. 상대방이 세션을 종료하고 나간 경우
                    elif method == "DELETE" and url == "/leave":
                        print(f"\n[세션 알림] {sender_id} 님이 세션을 종료했습니다.")
                        if sock in read_list: read_list.remove(sock)
                        if sender_id in session_members: session_members.remove(sender_id)
                        if sender_id in session_sockets: del session_sockets[sender_id]
                        sock.close()


# print functions
def print_commands():
    command = [
        "<Command>",
        "invite <username>",
        "send <username> <message>",
        "sendall <message>",
        "leave",
        "quit"
    ]

    print()
    print(command[0])
    for i in range(1, len(command)):
        print(f"{i}. {command[i]}")


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


# main
def main():
    global user_dict

    login()
    chat()

if __name__ == "__main__":
    main()