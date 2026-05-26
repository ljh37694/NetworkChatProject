import select
from socket import *
import json
from utils import parse_message, make_res_msg, is_valid_http_msg, make_req_msg

SERVER_PORT = 12000
BUFFER_SIZE = 1024
DB_FILE = "users.json"

server_socket: socket | None = None
user_dict: dict = {}
active_clients: dict = {}
socket_to_id: dict = {}
read_list: list[socket] = []

def reset_db():
	print(f"initialize {DB_FILE}")
	with open(DB_FILE, "w", encoding="utf-8") as f:
		json.dump({}, f)


def init():
	global server_socket

	server_socket = socket(AF_INET, SOCK_STREAM)
	server_socket.bind(('', SERVER_PORT))

	server_socket.listen(1)
	read_list.append(server_socket)
	print('The server is ready to receive')

	reset_db()


def send_user_dict_to_clients():
	active_sock: socket
	for uid, active_sock in active_clients.items():
		request_body = json.dumps(user_dict)
		request_msg = make_req_msg("PUT", "/users", request_body)
		active_sock.sendall(request_msg)


def handle_login(sock: socket, body: str):
	global user_dict

	# register user
	with open(DB_FILE, "r", encoding="utf-8") as f:
		users = json.load(f)
		user_info = json.loads(body)
		user_id = next(iter(user_info))
		user_info[user_id]["ip"] = sock.getpeername()[0]
		user_dict |= user_info

		users |= user_info

		f.close()

	with open(DB_FILE, "w", encoding="utf-8") as f:
		json.dump(users, f, indent=4)
		f.close()

	# response
	response_body = json.dumps(users)
	packet = make_res_msg(200, response_body)

	sock.send(packet)

	send_user_dict_to_clients()

	active_clients[user_id] = sock
	socket_to_id[sock] = user_id


def handle_users(sock: socket, body: str):
	global user_dict

	response_body = json.dumps(user_dict)
	response = make_res_msg(200, response_body)

	sock.sendall(response)

router = {
	"/login": handle_login,
	"/users": handle_users,
}


def run_server():
	while True:
		r_ready, _, _ = select.select(read_list, [], [])

		for sock in r_ready:
			# login 요청받았을 때
			if sock == server_socket:
				connection_socket, addr = server_socket.accept()
				request = connection_socket.recv(BUFFER_SIZE)
				header, body = parse_message(request)

				# 올바른 요청이 왔을 때 URL에 맞는 handler 실행
				if header.get("Status-Message") == "OK":
					read_list.append(connection_socket)
					reqeust_url = header.get("URL")

					handler = router[reqeust_url]
					if handler:
						handler(connection_socket, body)

				# 비정상적일 때
				else:
					response_msg = make_res_msg(400)
					connection_socket.sendall(response_msg)

			# 로그인 후 요청 hanlde 및 disconnection 확인
			else:
				try:
					request_msg = sock.recv(BUFFER_SIZE)
				except (ConnectionResetError, BrokenPipeError):
					request_msg = b''

				if not request_msg:
					# disconnect된 sock 삭제
					if sock in read_list:
						read_list.remove(sock)
						user_id = socket_to_id[sock]
						del active_clients[user_id]
						socket_to_id.pop(sock)
						del user_dict[user_id]
						sock.close()

						print(f"{user_id}와의 연결이 끊어졌습니다.")
						print(user_dict)

					try:
						with open(DB_FILE, "w", encoding="utf-8") as f:
							json.dump(user_dict, f)
					except Exception as e:
						print(f"[Error] DB 파일 최신화 실패: {e}")

					send_user_dict_to_clients()


def main():
	init()
	run_server()


if __name__ == "__main__":
	main()