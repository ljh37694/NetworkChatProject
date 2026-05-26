# login
## msg format
---
### Request
```text
POST /login HTTP/1.0\r\n
Content-Type: application/json\r\n
Content-Length: 45\r\n
\r\n
{"username": {"port": 9001}}
```

### Response
```text
HTTP/1.0 200 OK\r\n
Content-Type: application/json\r\n
Content-Length: 54\r\n
\r\n
[{"username": {"ip": "127.0.0.1", "port": 9001}}]
```

<br>

# Chat

## msg format
---
### Resquest
```text
CHAT /chat HTTP/1.0 \r\n
From: user1
Content-Length: 5\r\n
\r\n
HELLO
```

### Response
```text
HTTP/1.0 200 OK\r\n
From: user2\r\n
Content-Length: 0\r\n
\r\n
```