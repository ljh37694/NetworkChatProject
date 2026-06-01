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
session_members: dict[str, socket | None] = {}
session_connected: bool = False


"""
Utility Functions
"""
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


def make_socket(target_name: str) -> socket | None:
    if target_name in user_dict:
        target_info = user_dict.get(target_name)
        target_sock = socket(AF_INET, SOCK_STREAM)
        target_sock.connect((target_info.get("ip"), target_info.get("port")))

        return target_sock

    return None


def print_session_members(count: int = 5):
    tmp_list = [my_info.get("id")] + [key for key in session_members.keys()]
    length = len(tmp_list)

    if length == 0:
        print("현재 세션에 참여 중인 유저가 없습니다.")
        return

    print("<현재 세션에 참여 중인 유저 리스트>")
    for i in range(0, length, count):
        chunk = tmp_list[i: i + count]
        print("[" + ", ".join(chunk) + "]")


def print_commands():
    command = [
        "<Command>",
        "members",
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


"""
    핵심기능
"""
# login
def login():
    global user_dict, client_socket, my_info, session_connected

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

    if len(user_dict) < 2:
        session_connected = True
        print("세션이 생성되었습니다.")


def update_user_dict():
    global user_dict, client_socket

    send_packet(client_socket, "GET", "/users")

    header, body = receive_packet(client_socket)

    if header.get("Status-Code") == 200:
        user_dict = json.loads(body)


def disconnect_client():
    for sock in read_list:
        if sock != sys.stdin:
            sock.close()
    exit()


def invite_user(target_name: str):
    if not session_connected:
        print("현재 참여 중인 세션이 없습니다.")
        return

    # 없는 유저이거나 이미 세션에 있는 유저이면 return
    elif target_name not in user_dict:
        print(f"{target_name} 님은 현재 오프라인이거나 없는 유저입니다.")
        return

    elif target_name in session_members:
        print(f"{target_name} 님은 이미 세션에 있습니다.")
        return

    # 내 세션에 등록 및 select 감시 대상에 등록
    try:
        target_sock = make_socket(target_name)

        if target_sock is None:
            print(f"[{target_name}] 님과 연결할 수 없습니다. (오프라인)")
            return

        read_list.append(target_sock)

        send_packet(target_sock, "POST", "/invite", json.dumps([mem for mem in session_members.keys()]), {"From": my_info["id"]})
        header, body = receive_packet(target_sock)

        # 상대가 초대를 정상적으로 받았을 때
        if int(header.get("Status-Code")) == 200:
            # target 제외 새로운 member 추가됐다고 member들에게 알리기
            for mem in session_members.keys():
                if mem != my_info.get("id"):
                    if session_members[mem] is None:
                        session_members[mem] = make_socket(mem)
                    send_packet(session_members[mem], "PUT", "/session/update", target_name)

            session_members[target_name] = target_sock

            print(f"{target_name} 님을 세션에 성공적으로 초대했습니다.")

    except Exception as e:
        print(f"세션 초대 실패: {e}")


def leave_session():
    global session_connected

    print("현재 세션을 종료합니다.")

    for peer, peer_sock in session_members.items():
        if peer_sock is None:
            peer_sock = make_socket(peer)

        if peer_sock:
            try:
                send_packet(peer_sock, "DELETE", "/leave", my_info.get("id"), {"From": my_info.get("id")})

                if peer_sock in read_list:
                    read_list.remove(peer_sock)
                peer_sock.close()

            except Exception as e:
                print(e)

    # 세션 비우기
    session_members.clear()
    session_connected = False


def send_message(target_name: str, message: str):
    if target_name in session_members:
        if session_members[target_name] is None:
            target_sock = make_socket(target_name)

            if target_sock is None:
                print(f"[{target_name}] 님과 연결할 수 없습니다. (오프라인)")
                return

            session_members[target_name] = target_sock
            read_list.append(target_sock)

        send_packet(
            session_members[target_name],
            "POST",
            "/send", message,
            extra_header={"From": my_info["id"]}
        )

    else:
        print(f"[{target_name} 님은 현재 세션에 없습니다.")


def sendall_message(message: str):
    for mem in session_members:
        if mem != my_info.get("id"):
            send_message(mem, message)


router = {
    "/invite": "",
    "/session/update": "",
    "/send": "",
    "/leave": ""
}


def start_run():
    global my_info, client_socket, user_dict, read_list, session_connected

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
                if cmd[0] == "members":
                    print_session_members()

                elif cmd[0] == "invite":
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

            # handshake
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

                    read_list.remove(sock)
                    for name, act_sock in session_members.items():
                        if act_sock == sock:
                            del session_members[name]
                            print(f"\n{name} 님과의 연결이 끊겼습니다.")
                            break
                    continue

                # receive chat
                if "Method" in header:
                    method = header.get("Method")
                    url = header.get("URL")
                    sender_id = header.get("From")

                    # session 초대를 받았을 때
                    if method == "POST" and url == "/invite":
                        members_list = json.loads(body)

                        # 나를 제외한 handshake 및 내 session_members에 등록
                        session_members[sender_id] = sock
                        for mem in members_list:
                            if mem != my_info.get("id") and mem != sender_id:
                                session_members[mem] = None

                        print(f"\n[세션 알림] {sender_id} 님의 메신저 세션에 초청되어 입장되었습니다!")
                        session_connected = True
                        print_session_members()
                        sock.sendall(make_res_msg(200))

                    elif method == "PUT" and url == "/session/update":
                        new_user = body

                        if new_user not in session_members:
                            session_members[new_user] = None

                        print(f"{body} 님이 세션에 참가했습니다.")
                        sock.sendall(make_res_msg(200))

                    # B. 상대방이 세션 전체에 메시지를 뿌린 경우
                    elif method == "POST" and url == "/send":
                        print(f"[{sender_id}]: {body}")

                        if session_members[sender_id] is None:
                            session_members[sender_id] = sock

                        sock.sendall(make_res_msg(200))

                    # C. 상대방이 세션을 종료하고 나간 경우
                    elif method == "DELETE" and url == "/leave":
                        print(f"\n[세션 알림] {sender_id} 님이 세션을 종료했습니다.")
                        if sock in read_list: read_list.remove(sock)
                        if sender_id in session_members: del session_members[sender_id]
                        sock.close()


# main
def main():
    try:
        login()
        start_run()

    except Exception as e:
        for sock in read_list:
            if sock != sys.stdin:
                try:
                    sock.close()
                except Exception as err:
                    print(err)
        print(e)

if __name__ == "__main__":
    main()