def parse_message(raw_bytes: bytes) -> tuple[dict, str | None]:
	delimiter = b"\r\n\r\n"
	if delimiter not in raw_bytes:
		return {"Status-Message": "INCOMPLETE"}, None # 데이터가 덜 전송됐을 때

	# 1. Header bytes와 Body bytes를 분리
	header_bytes, body_bytes = raw_bytes.split(delimiter, 1)
	try:
		header_text = header_bytes.decode()
	except UnicodeDecodeError:
		return {"Status-Message": "BAD_REQUEST", "Reason": "Header Decode Error"}, None

	# 2. header를 \r\n 기준으로 분리 및 header field parsing
	lines = header_text.split("\r\n")
	if not lines or lines[0] == "":
		return {"Status-Message": "BAD_REQUEST", "Reason": "Empty Request"}, None

	start_line = lines[0].split()
	if len(start_line) < 3:
		return {"Status-Message": "BAD_REQUEST", "Reason": "Invalid Format"}, None

	# print(f"start line: {start_line}")
	
	# request msg일 때
	if not "HTTP" in start_line[0]:
		headers = {"Status-Message": "OK", "Method": start_line[0], "URL": start_line[1]}
		
	# response msg일 때
	else:
		headers = {
			"HTTP": start_line[0],
			"Status-Code": int(start_line[1]),
			"Status-Message": start_line[2],
		}
		
	for line in lines[1:]:
		if not line:
			continue
		if ":" not in line:
			return {"Status-Message": "BAD_REQUEST", "Reason": "Invalid Header Format"}, None

		key, value = line.split(":", 1)
		headers[key.strip()] = value.strip()

	# 3. Content-Length 검증 및 바디 구하기
	try:
		content_length = int(headers.get("Content-Length", 0))
	except ValueError:
		return {"Status-Message": "BAD_REQUEST", "Reason": "Invalid Content-Length Value"}, None

	if len(body_bytes) < content_length:
		return {"Status-Message": "INCOMPLETE"}, None

	body_bytes = body_bytes[:content_length]

	try:
		body_text = body_bytes.decode()
	except UnicodeDecodeError:
		return {"Status-Message": "BAD_REQUEST", "Reason": "Body Decode Error"}, None

	return headers, body_text


def make_req_msg(method: str, url: str, body: str = "", extra_field: dict[str, str] = None) -> bytes:
	body_bytes = body.encode()

	header_lines = [
		f"{method} {url} HTTP/1.0",
		"Content-Type: application/json",
		f"Content-Length: {len(body_bytes)}",
	]

	if extra_field:
		for key, value in extra_field.items():
			header_lines.append(f"{key}: {value}")
	header = "\r\n".join(header_lines) + "\r\n\r\n"

	header_bytes = header.encode()
	body_bytes = body.encode()

	return header_bytes + body_bytes


def make_res_msg(status: int, body: str = "", extra_field: dict[str, str] = None) -> bytes:
	status_messages = {
		"200": "OK",
		"400": "Bad Request",
		"500": "Server Error"
	}

	header_lines = [
		f"HTTP/1.0 {status} {status_messages[str(status)]}",
		"Content-Type: application/json",
		f"Content-Length: {len(body)}",
	]

	if extra_field:
		for key, value in extra_field.items():
			header_lines.append(f"{key}: {value}")
	header = "\r\n".join(header_lines) + "\r\n\r\n"

	header_bytes = header.encode()
	body_bytes = body.encode()

	return header_bytes + body_bytes


def is_valid_http_msg(http_msg: bytes) -> bool:
	header, body = parse_message(http_msg)

	if header["Status-Message"] == "OK":
		return True

	return False
