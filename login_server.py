from socket import *
import json

server_port = 12000
BUFFER_SIZE = 1024
server_socket = socket(AF_INET, SOCK_STREAM)
server_socket.bind(('', server_port))
DB_FILE = "users.json"

print(f"[시스템] 서버가 시작되어 {DB_FILE} 파일을 초기화합니다.")
with open(DB_FILE, "w", encoding="utf-8") as f:
    json.dump({ "online": [] }, f)


server_socket.listen(1)
print('The server is ready to receive')

def parse_http_msg(raw_bytes):
	delimiter = b"\r\n\r\n"
	if delimiter not in raw_bytes:
		return {"status": "INCOMPLETE"}, None # 데이터가 덜 전송됐을 때

	# 1. Header bytes와 Body bytes를 분리
	header_bytes, body_bytes = raw_bytes.split(delimiter, 1)
	try:
		header_text = header_bytes.decode()
	except UnicodeDecodeError:
		return {"status": "BAD_REQUEST", "reason": "Header Decode Error"}, None

	# 2. header를 \r\n 기준으로 분리 및 header field parsing
	lines = header_text.split("\r\n")
	if not lines or lines[0] == "":
		return {"status": "BAD_REQUEST", "reason": "Empty Request"}, None

	start_line = lines[0].split()
	if len(start_line) < 3:
		return {"status": "BAD_REQUEST", "reason": "Invalid Format"}, None

	headers = {"status": "OK", "method": start_line[0]}
	for line in lines[1:]:
		if not line:
			continue
		if ":" not in line:
			return {"status": "BAD_REQUEST", "reason": "Invalid Header Format"}

		key, value = line.split(":", 1)
		headers[key.strip()] = value.strip()

	# 3. Content-Length 검증 및 바디 구하기
	try:
		content_length = int(headers.get("Content-Length", 0))
	except ValueError:
		return {"status": "BAD_REQUEST", "reason": "Invalid Content-Length Value"}, None

	if len(body_bytes) < content_length:
		return {"status": "INCOMPLETE"}, None

	body_bytes = body_bytes[:content_length]

	try:
		body_text = body_bytes.decode()
	except UnicodeDecodeError:
		return {"status": "BAD_REQUEST", "reason": "Body Decode Error"}, None

	return headers, body_text


while True:
	connection_socket, addr = server_socket.accept()
	data = connection_socket.recv(BUFFER_SIZE)

	header, body = parse_http_msg(data)

	print(header)
	print(json.loads(body))
	print(addr)

	if header["status"] == "INCOMPLETE":
		continue

	elif header["status"] == "BAD_REQUEST":
		response_header = (
			"HTTP/1.0 400 Bad Request\r\n"
			"Content-Length: 0\r\n"
			"Connection: close\r\n\r\n"
		)

		connection_socket.send(response_header.encode())
		connection_socket.close()
	else:
		# register user
		with open(DB_FILE, "r", encoding="utf-8") as f:
			users = json.load(f)
			user_info = json.loads(body)
			user_info["ip"] = addr[0]
			users["online"].append(user_info)

			f.close()

		with open(DB_FILE, "w", encoding="utf-8") as f:
			json.dump(users, f, indent=4)
			f.close()

		response_body = json.dumps(users)

		response_header = (
			"HTTP/1.0 200 OK\r\n"
			"Content-Type: application/json\r\n"
			f"Content-Length {len(response_body)}\r\n"
			"\r\n"
		)

		res_header_bytes = response_header.encode()
		res_body_bytes = response_body.encode()

		packet = res_header_bytes + res_body_bytes

		connection_socket.send(packet)
		connection_socket.close()


	""" Request
	POST /login HTTP/1.0\r\n
	Content-Type: application/json\r\n
	Content-Length: 45\r\n
	\r\n
	{"id": "junghoon", "ip": "127.0.0.1", "port": 9001}
	"""

	""" Response
	HTTP/1.0 200 OK\r\n
	Content-Type: application/json\r\n
	Content-Length: 54\r\n
	\r\n
	{"user_b": {"ip": "127.0.0.1", "port": 9002}}
	"""

with open("users.json", "w", encoding="utf-8") as f:
	f.write("")
	f.close()