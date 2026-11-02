import socket
import threading
import json
import time

class LANServer:
    def __init__(self, crypto_manager, host="0.0.0.0", port=54321, broadcast_port=54322):
        self.crypto = crypto_manager
        self.host = host
        self.port = port
        self.broadcast_port = broadcast_port
        self.clients = {}
        self.on_message_received = None
        self.on_device_found = None
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._start_tcp_server, daemon=True).start()
        threading.Thread(target=self._listen_broadcast, daemon=True).start()
        threading.Thread(target=self._broadcast_presence, daemon=True).start()

    def _start_tcp_server(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(10)
        while self.running:
            try:
                conn, addr = server_socket.accept()
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
            except Exception:
                break

    def _handle_client(self, conn, addr):
        try:
            data = conn.recv(4096 * 1024).decode("utf-8")
            payload = json.loads(data)
            if payload.get("type") == "message":
                encrypted_msg = payload["encrypted_content"]
                sender_ip = addr[0]
                if self.on_message_received:
                    try:
                        plaintext = self.crypto.decrypt_message(encrypted_msg)
                        self.on_message_received(sender_ip, plaintext, True)
                    except Exception as e:
                        self.on_message_received(sender_ip, f"[Lỗi giải mã]: {str(e)}", False)
            elif payload.get("type") == "discovery":
                resp = {
                    "type": "discovery_ack",
                    "ip": self._get_local_ip(),
                    "port": self.port,
                    "fingerprint": self.crypto.get_key_fingerprint()
                }
                conn.send(json.dumps(resp).encode())
        except Exception:
            pass
        finally:
            conn.close()

    def _listen_broadcast(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self.broadcast_port))
        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode())
                if msg.get("action") == "ping" and addr[0] != self._get_local_ip():
                    if self.on_device_found:
                        self.on_device_found(addr)
            except Exception:
                continue

    def _broadcast_presence(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self.running:
            try:
                msg = json.dumps({"action": "announce", "port": self.port, "fingerprint": self.crypto.get_key_fingerprint()})
                sock.sendto(msg.encode(), ("<broadcast>", self.broadcast_port))
                time.sleep(10)
            except Exception:
                time.sleep(2)

    def send_message(self, target_ip, target_port, recipient_pem, message):
        try:
            encrypted = self.crypto.encrypt_message(message, recipient_pem)
            payload = json.dumps({"type": "message", "encrypted_content": encrypted})
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((target_ip, target_port))
            sock.send(payload.encode())
            sock.close()
            return True, "Đã gửi"
        except Exception as e:
            return False, str(e)

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def stop(self):
        self.running = False