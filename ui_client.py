import tkinter as tk
from tkinter import messagebox
import threading
import select
import json
from socket import socket

# client 소켓 엔진의 자원 임포트
import client
from utils import parse_message, make_res_msg

# 전역 감시 리스트 객체
read_list: list[socket] = []


class MessengerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("P2P 메신저 시스템")
        self.root.geometry("400x300")  # 초기 로그인 창은 아담하게 설정

        self.current_target = None  # 선택된 채팅 상대방 이름 기억

        # -----------------------------------------------------------------
        # [화면 구성요소 컨테이너 정의]
        # -----------------------------------------------------------------
        # 1. 로그인 화면을 담을 프레임
        self.login_frame = tk.Frame(self.root, bg="#fafafa")
        self.login_frame.pack(fill=tk.BOTH, expand=True)

        # 2. 메인 대화방 화면을 담을 프레임 (초기에는 숨겨둠)
        self.main_frame = tk.Frame(self.root, bg="#ffffff")

        # 로그인 화면 UI 조립 시작
        self.setup_login_ui()

    # -----------------------------------------------------------------
    # 1단계: 로그인 화면 UI 디자인 및 컴포넌트 배치
    # -----------------------------------------------------------------
    def setup_login_ui(self):
        # 중앙 정렬용 내부 컨테이너
        center_frame = tk.Frame(self.login_frame, bg="#fafafa")
        center_frame.pack(expand=True)

        title_label = tk.Label(center_frame, text="P2P Messenger 로그인", bg="#fafafa", font=("Arial", 14, "bold"))
        title_label.pack(pady=15)

        # 아이디 입력 영역
        id_frame = tk.Frame(center_frame, bg="#fafafa")
        id_frame.pack(pady=5, fill=tk.X)
        tk.Label(id_frame, text="유저 아이디 : ", bg="#fafafa", width=12, anchor="w", font=("Arial", 10)).pack(side=tk.LEFT)
        self.entry_id = tk.Entry(id_frame, font=("Arial", 10), width=20)
        self.entry_id.pack(side=tk.LEFT, padx=5)
        self.entry_id.focus()  # 키보드 포커스 시작점 지정

        # 포트 번호 입력 영역
        port_frame = tk.Frame(center_frame, bg="#fafafa")
        port_frame.pack(pady=5, fill=tk.X)
        tk.Label(port_frame, text="사용할 포트 : ", bg="#fafafa", width=12, anchor="w", font=("Arial", 10)).pack(
            side=tk.LEFT)
        self.entry_port = tk.Entry(port_frame, font=("Arial", 10), width=20)
        self.entry_port.pack(side=tk.LEFT, padx=5)

        # 엔터키를 치면 바로 로그인 시도되도록 매핑
        self.entry_port.bind("<Return>", lambda event: self.try_login())

        # 로그인 버튼
        self.btn_login = tk.Button(center_frame, text="접속하기", width=22, bg="#2196f3", fg="black",
                                   activebackground="#1e88e5", font=("Arial", 10, "bold"), command=self.try_login)
        self.btn_login.pack(pady=20)

    # -----------------------------------------------------------------
    # 로그인 검증 및 화면 전환 트리거 실행 함수
    # -----------------------------------------------------------------
    def try_login(self):
        user_id = self.entry_id.get().strip()
        port_str = self.entry_port.get().strip()

        if not user_id or not port_str:
            messagebox.showwarning("입력 오류", "아이디와 포트 번호를 빠짐없이 입력해주세요.")
            return

        try:
            port_num = int(port_str)
        except ValueError:
            messagebox.showwarning("입력 오류", "포트 번호는 유효한 숫자 형식이어야 합니다.")
            return

        # 백엔드 core 소켓 엔진에 로그인 트랜잭션 요청 전달
        try:
            res_header = client.login(user_id, port_num)

            # 로그인 성공 시 가동되는 화면 체인지 시퀀스
            self.show_main_chat_ui(user_id)

        except Exception as e:
            messagebox.showerror("서버 에러", f"서버 연결 또는 로그인에 실패했습니다:\n{e}")

    # -----------------------------------------------------------------
    # 2단계: 메인 채팅방 화면 언팩 및 렌더링 전환 구역
    # -----------------------------------------------------------------
    def show_main_chat_ui(self, user_id):
        # ① 로그인 화면 컨테이너 프레임을 화면에서 완전히 파괴/제거합니다.
        self.login_frame.pack_forget()
        self.login_frame.destroy()

        # ② 메인 윈도우 창의 크기를 시원한 멀티 뷰 규격으로 확장 변경합니다.
        self.root.geometry("650x450")
        self.root.title(f"P2P Messenger - [{user_id}]")

        # ③ 메인 대화 패널 팩을 채워 펼칩니다.
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # -----------------------------------------------------------------
        # 레이아웃 분할 배치 (좌측 목록 / 우측 채팅창)
        # -----------------------------------------------------------------
        # 좌측 영역 사이드 패널
        self.left_panel = tk.Frame(self.main_frame, width=200, bg="#f0f0f0", bd=1, relief=tk.SOLID)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.left_panel.pack_propagate(False)

        # 우측 영역 메인 패널
        self.right_panel = tk.Frame(self.main_frame, bg="#ffffff")
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 좌측 리스트박스 컴포넌트 빌드
        self.list_label = tk.Label(self.left_panel, text="온라인 유저 목록", bg="#f0f0f0", font=("Arial", 11, "bold"))
        self.list_label.pack(pady=10)

        self.user_listbox = tk.Listbox(self.left_panel, selectmode=tk.SINGLE, font=("Arial", 10), bd=0)
        self.user_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.user_listbox.bind("<<ListboxSelect>>", self.on_user_selected)

        # 우측 대화방 상단 투명 헤더바
        self.chat_title = tk.Label(self.right_panel, text="대화 상대를 목록에서 선택하세요.", bg="#e1e1e1",
                                   font=("Arial", 11, "bold"), anchor="w", padx=10)
        self.chat_title.pack(fill=tk.X, ipady=8)

        # 우측 대화 출력용 스크롤 스택 텍스트박스
        self.txt_frame = tk.Frame(self.right_panel)
        self.txt_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.scrollbar = tk.Scrollbar(self.txt_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.chat_area = tk.Text(self.txt_frame, yscrollcommand=self.scrollbar.set, state=tk.DISABLED,
                                 font=("Arial", 10), wrap=tk.WORD)
        self.chat_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.chat_area.yview)

        # 우측 하단 텍스트 인풋 콤보
        self.input_frame = tk.Frame(self.right_panel, bg="#ffffff")
        self.input_frame.pack(fill=tk.X, padx=10, pady=10)

        self.entry_msg = tk.Entry(self.input_frame, font=("Arial", 10))
        self.entry_msg.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.entry_msg.bind("<Return>", self.send_ui_message)

        self.btn_send = tk.Button(self.input_frame, text="전송", width=8, command=self.send_ui_message, bg="#ffeb3b")
        self.btn_send.pack(side=tk.RIGHT, padx=5)

        # -----------------------------------------------------------------
        # ④ [소켓 엔진 결합] P2P 포트 리스닝 및 실시간 비동기 백그라운드 스레드 가동
        # -----------------------------------------------------------------
        global read_list
        p2p_sock = client.init_p2p()

        # 감시 타깃 배열 셋업
        read_list = [p2p_sock, client.client_socket]

        # 초기 유저 목록 렌더링 반영
        self.refresh_user_list()

        # 데이터 수신용 비동기 스레드 실행
        net_thread = threading.Thread(target=self.socket_receive_loop, daemon=True)
        net_thread.start()

    # -----------------------------------------------------------------
    # 기능 유틸리티 제어 함수군
    # -----------------------------------------------------------------
    def refresh_user_list(self):
        """client.user_dict 동기화 명단 새로고침"""
        self.user_listbox.delete(0, tk.END)
        for user in client.user_dict:
            if user != client.my_info.get("id"):
                self.user_listbox.insert(tk.END, user)

    def on_user_selected(self, event):
        """유저 목록 클릭 타깃팅 체인지"""
        widget = event.widget
        selection = widget.curselection()
        if not selection:
            return
        self.current_target = widget.get(selection[0])
        self.chat_title.config(text=f"[{self.current_target}] 님과의 실시간 P2P 대화방")

        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete("1.0", tk.END)
        self.chat_area.insert(tk.END, f"--- {self.current_target} 님과의 대화 통로 연결 활성화 ---\n")
        self.chat_area.config(state=tk.DISABLED)

    def append_chat_message(self, sender: str, msg: str):
        """채팅창 텍스트 라인 실시간 갱신"""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"[{sender}]: {msg}\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def send_ui_message(self, event=None):
        """전송 액션 핸들러"""
        if not self.current_target:
            messagebox.showwarning("경고", "목록에서 대화 상대를 먼저 선택하세요.")
            return

        message = self.entry_msg.get().strip()
        if not message:
            return

        success = client.send_p2p_message(self.current_target, message)
        if success:
            self.append_chat_message("나", message)
            self.entry_msg.delete(0, tk.END)
        else:
            messagebox.showerror("전송 실패", "온라인 유저 주소 정보 매칭 실패.")

    # -----------------------------------------------------------------
    # 비동기 소켓 I/O 패킷 수신 루프 (독립 스레드)
    # -----------------------------------------------------------------
    def socket_receive_loop(self):
        global read_list
        while True:
            r_ready, _, _ = select.select(read_list, [], [])

            sock: socket
            for sock in r_ready:
                # ① 중앙 서버로부터의 실시간 유저 업데이트 패킷 핸들링
                if sock == client.client_socket:
                    request = sock.recv(client.BUFFER_SIZE)
                    if not request:
                        print("[시스템] 서버 세션 단절")
                        read_list.remove(sock)
                        continue

                    header, body = parse_message(request)
                    if header.get("Status-Message") == "OK" or header.get("Method") == "UPDATE":
                        client.user_dict = json.loads(body)
                        self.refresh_user_list()  # 리스트박스 갱신
                        sock.sendall(make_res_msg(200))
                    else:
                        sock.sendall(make_res_msg(400))

                # ② 다른 피어로부터 신규 노크 커넥션이 인입된 경우 (Inbound P2P Handshake)
                elif sock == client.p2p_listen_sock:
                    connection_sock, address = client.p2p_listen_sock.accept()
                    read_list.append(connection_sock)

                # ③ 기존에 결합되어 대화방이 활성화된 피어가 패킷을 보내온 경우
                else:
                    message = sock.recv(client.BUFFER_SIZE)
                    if not message:
                        read_list.remove(sock)
                        for name, act_sock in list(client.active_sockets.items()):
                            if act_sock == sock:
                                del client.active_sockets[name]
                                break
                        continue

                    header, body = parse_message(message)

                    if "Method" in header:
                        sender_name = header.get("From", "Unknown")

                        if sender_name not in client.active_sockets:
                            client.active_sockets[sender_name] = sock

                        # 현재 바라보고 있는 대화창의 주인과 송신자 주체가 일치하면 화면 렌더링
                        if self.current_target == sender_name:
                            self.append_chat_message(sender_name, body)
                        else:
                            print(f"\n[알림 - 백그라운드] {sender_name}님 메시지: {body}")

                        sock.sendall(make_res_msg(200))


if __name__ == "__main__":
    root = tk.Tk()
    app = MessengerGUI(root)
    root.mainloop()