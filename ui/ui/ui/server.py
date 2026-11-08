import datetime
import glob
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import socket
import ssl
import sys
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("LANCHAT_DATA") or os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "server.json")
CERT_PATH = os.path.join(DATA_DIR, "cert.pem")
KEY_PATH = os.path.join(DATA_DIR, "key.pem")
CA_CERT_PATH = os.path.join(DATA_DIR, "ca.pem")
CA_KEY_PATH = os.path.join(DATA_DIR, "ca-key.pem")
PORT = int(os.environ.get("LANCHAT_PORT", 8443))
LOCAL_PORT = int(os.environ.get("LANCHAT_LOCAL_PORT", 8000))
ONLINE_SECONDS = 30
MAX_BODY = 1024 * 1024
MAX_GROUP = 50
MAX_FAILS = 5
MAX_SIGNUPS_PER_HOUR = 10
PAIR_SECONDS = 300  # đủ thời gian cho bước bỏ qua cảnh báo chứng chỉ trên điện thoại
# Trang được phép dùng máy chủ này từ địa chỉ khác (bản trên GitHub Pages)
PUBLIC_URL_FILE = os.path.join(DATA_DIR, "public_url.txt")
SERVER_ID_FILE = os.path.join(DATA_DIR, "server_id")
ALLOWED_ORIGINS = {"https://thanhesssd.github.io"} | set(filter(None, os.environ.get("LANCHAT_ORIGINS", "").split(",")))
LOCK_SECONDS = 60
SESSION_SECONDS = 30 * 24 * 3600
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}


class Store:
    """Tài khoản, nhóm và tin nhắn. Máy chủ chỉ giữ dữ liệu đã mã hóa, không có khóa để đọc."""

    def __init__(self):
        self.cond = threading.Condition()
        self.users = {}
        self.groups = {}
        self.messages = []
        self.seq = 0
        self.friends = set()
        self.requests = set()
        self.sessions = {}
        self.fails = {}
        self.signups = {}
        self.pairs = {}
        self.last_seen = {}
        self.recent_mids = {}  # (tài khoản, mã tin) -> seq, để không lưu trùng khi gửi lại
        self.delivered = {}  # ID tài khoản -> seq tin cuối cùng máy đó đã xác nhận nhận được
        self.rseq = 0  # tăng mỗi khi có xác nhận mới, để đánh thức máy gửi đang chờ
        if os.path.exists(DB_PATH):
            with open(DB_PATH, encoding="utf-8") as f:
                db = json.load(f)
            self.users = {int(k): v for k, v in db["users"].items()}
            self.groups = {int(k): v for k, v in db["groups"].items()}
            self.messages = db["messages"]
            self.seq = db["seq"]
            self.friends = {tuple(p) for p in db.get("friends", [])}
            self.requests = {tuple(p) for p in db.get("requests", [])}
            self.sessions = {k: tuple(v) for k, v in db.get("sessions", {}).items() if v[1] > time.time()}
            self.delivered = {int(k): v for k, v in db.get("delivered", {}).items()}

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = DB_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"users": self.users, "groups": self.groups, "messages": self.messages, "seq": self.seq,
                       "friends": sorted(self.friends), "requests": sorted(self.requests), "sessions": self.sessions,
                       "delivered": self.delivered}, f)
        os.replace(tmp, DB_PATH)

    def bump(self):
        self.seq += 1
        self.save()
        self.cond.notify_all()

    def find_user(self, name):
        """Tìm theo tên đúng, mã số (1001 hoặc #1001), hoặc tên rút gọn của Địa chỉ LAN Chat (nguyen.van.an)."""
        key = clean_name(name).lower()
        user = next((u for u in self.users.values() if u["name"].lower() == key), None)
        if user:
            return user
        num = key.lstrip("#")
        if num.isdigit():
            return self.users.get(int(num))
        matches = [u for u in self.users.values() if handle_of(u["name"]) == handle_of(key)]
        return matches[0] if len(matches) == 1 else None

    def friends_of(self, uid):
        return {b if a == uid else a for a, b in self.friends if uid in (a, b)}

    def relation(self, uid, other):
        if pair(uid, other) in self.friends:
            return "friend"
        if (other, uid) in self.requests:
            return "incoming"
        return "outgoing" if (uid, other) in self.requests else "none"


def handle_of(name):
    """Tên rút gọn dùng trong Địa chỉ LAN Chat: bỏ dấu, chữ thường, nối bằng dấu chấm."""
    text = unicodedata.normalize("NFD", name.lower().replace("đ", "d"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", ".", text).strip(".")


def clean_name(name):
    return unicodedata.normalize("NFC", " ".join(name.split()))


def pair(a, b):
    return (a, b) if a < b else (b, a)


def hash_password(pass_hash, salt):
    return hashlib.pbkdf2_hmac("sha256", pass_hash.encode(), bytes.fromhex(salt), 200000).hex()


def public_user(store, user):
    online = time.time() - store.last_seen.get(user["id"], 0) < ONLINE_SECONDS
    return {"id": user["id"], "name": user["name"], "pub": user["pub"], "online": online}


def brief_user(store, uid):
    user = public_user(store, store.users[uid])
    del user["pub"]
    return user


class Handler(BaseHTTPRequestHandler):
    store = None

    def log_message(self, *args):
        pass

    def cors_headers(self):
        origin = self.headers.get("Origin", "")
        if origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        # Trình duyệt hỏi trước khi trang GitHub gọi vào máy chủ trong mạng nội bộ
        if not urlparse(self.path).path.startswith("/api/") or not origin_allowed(self.headers.get("Origin", "")):
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(204)
        self.cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Token")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY:
            raise ValueError("Dữ liệu quá lớn")
        return json.loads(self.rfile.read(length) or b"{}")

    def client_ip(self):
        # Qua đường hầm Cloudflare mọi kết nối đều đến từ 127.0.0.1, địa chỉ thật nằm trong header
        ip = self.client_address[0]
        return self.headers.get("CF-Connecting-IP", ip) if ip == "127.0.0.1" else ip

    def current_user(self):
        key = hashlib.sha256(self.headers.get("X-Token", "").encode()).hexdigest()
        session = self.store.sessions.get(key)
        return session[0] if session and session[1] > time.time() else None

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/health":
            return self.send_json({"ok": True, "ip": primary_ip(), "port": PORT, "id": server_id(),
                                   "lan": [f"{ip}:{PORT}" for ip in local_ips() if not ip.startswith("127.")],
                                   "public": public_url()})
        if url.path == "/ca.crt":
            return self.serve_ca()
        if url.path == "/api/pair/status":
            return self.handle_pair_status(parse_qs(url.query))
        if url.path == "/api/vault":
            return self.handle_vault_get()
        if url.path == "/api/ca":
            return self.handle_ca()
        if url.path == "/api/sync":
            return self.handle_sync(parse_qs(url.query))
        if url.path == "/api/users":
            return self.handle_users(parse_qs(url.query))
        self.serve_static(unquote(url.path))

    def handle_ca(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes

        with open(CA_CERT_PATH, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        self.send_json({"subject": cert.subject.rfc4514_string(), "sha256": cert.fingerprint(hashes.SHA256()).hex().upper(),
                        "sha1": cert.fingerprint(hashes.SHA1()).hex().upper(), "until": cert.not_valid_after_utc.strftime("%d/%m/%Y"),
                        "ip": primary_ip(), "port": PORT})

    def serve_ca(self):
        # Chỉ là chứng chỉ công khai, để máy khác cài một lần và không còn cảnh báo
        with open(CA_CERT_PATH, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/x-x509-ca-cert")
        self.send_header("Content-Disposition", 'attachment; filename="LAN-Chat-CA.crt"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path):
        # Chỉ phục vụ file giao diện ở thư mục gốc, không lộ mã Python hay thư mục data
        name = path.lstrip("/") or next(iter(glob.glob("*Chat LAN*.html", root_dir=BASE_DIR)), "index.html")
        full = os.path.join(BASE_DIR, name)
        ext = os.path.splitext(name)[1].lower()
        if "/" in name or "\\" in name or ext not in STATIC_TYPES or not os.path.isfile(full):
            return self.send_json({"error": "Không tìm thấy trang"}, 404)
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", STATIC_TYPES[ext])
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        routes = {"/api/register": self.handle_register, "/api/login": self.handle_login,
                  "/api/send": self.handle_send, "/api/group": self.handle_group,
                  "/api/group/add": self.handle_group_add, "/api/group/leave": self.handle_group_leave,
                  "/api/friend": self.handle_friend, "/api/friend/scan": self.handle_friend_scan,
                  "/api/friend/code": self.handle_friend_code, "/api/logout": self.handle_logout, "/api/ack": self.handle_ack,
                  "/api/pair/create": self.handle_pair_create, "/api/pair/claim": self.handle_pair_claim,
                  "/api/vault": self.handle_vault_put}
        route = routes.get(urlparse(self.path).path)
        if not route:
            return self.send_json({"error": "Không tìm thấy"}, 404)
        try:
            route(self.read_json())
        except (ValueError, KeyError, TypeError):
            self.send_json({"error": "Dữ liệu gửi lên không hợp lệ"}, 400)

    def session(self, user, extra=None):
        token = secrets.token_hex(24)
        with self.store.cond:
            self.store.sessions[hashlib.sha256(token.encode()).hexdigest()] = (user["id"], time.time() + SESSION_SECONDS)
            user.setdefault("code", secrets.token_urlsafe(12))
            self.store.last_seen[user["id"]] = time.time()
            self.store.save()
        self.send_json({"token": token, "id": user["id"], "name": user["name"], "pub": user["pub"], "priv": user["priv"],
                        "code": user["code"], **(extra or {})})

    def handle_register(self, body):
        name = clean_name(body["name"])
        if not 2 <= len(name) <= 60:
            return self.send_json({"error": "Tên tài khoản cần từ 2 đến 60 ký tự"}, 400)
        if not re.fullmatch(r"[0-9a-f]{64}", body["passHash"]):
            return self.send_json({"error": "Mật khẩu không hợp lệ"}, 400)
        with self.store.cond:
            ip, now = self.client_ip(), time.time()
            recent = [t for t in self.store.signups.get(ip, []) if now - t < 3600]
            if len(recent) >= MAX_SIGNUPS_PER_HOUR:
                return self.send_json({"error": "Địa chỉ này đã tạo nhiều tài khoản. Hãy thử lại sau"}, 429)
            self.store.signups[ip] = recent + [now]
            if self.store.find_user(name):
                return self.send_json({"error": "Tên này đã có tài khoản. Hãy đăng nhập hoặc chọn tên khác"}, 409)
            salt = secrets.token_hex(16)
            uid = max(self.store.users, default=1000) + 1
            user = {"id": uid, "name": name, "salt": salt, "hash": hash_password(body["passHash"], salt),
                    "pub": body["pub"], "priv": body["priv"]}
            self.store.users[uid] = user
            self.store.bump()
        self.session(user)

    def handle_login(self, body):
        store = self.store
        key = (clean_name(body["name"]).lower(), self.client_ip())
        with store.cond:
            user = store.find_user(body["name"])
            count, until = store.fails.get(key, (0, 0))
        if until > time.time():
            wait = int(until - time.time()) + 1
            return self.send_json({"error": f"Sai mật khẩu nhiều lần. Hãy thử lại sau {wait} giây"}, 429)
        if not user or not hmac.compare_digest(user["hash"], hash_password(body["passHash"], user["salt"])):
            count += 1
            with store.cond:
                store.fails[key] = (0, time.time() + LOCK_SECONDS) if count >= MAX_FAILS else (count, 0)
            return self.send_json({"error": "Sai tên tài khoản hoặc mật khẩu"}, 401)
        with store.cond:
            store.fails.pop(key, None)
        self.session(user)

    def device_name(self):
        ua = self.headers.get("User-Agent", "")
        os_name = next((n for k, n in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows"),
                                         ("Mac OS", "macOS"), ("Linux", "Linux")) if k in ua), "Thiết bị")
        browser = next((n for k, n in (("Edg/", "Edge"), ("CriOS", "Chrome"), ("Chrome/", "Chrome"), ("Firefox/", "Firefox"),
                                         ("Safari/", "Safari")) if k in ua), "trình duyệt")
        return f"{os_name} · {browser}"

    def handle_pair_create(self, body):
        """Máy tính tạo mã kết nối dùng một lần. Khóa riêng đã được mã hóa bằng khóa chỉ nằm trong mã QR."""
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        blob = {"iv": str(body["blob"]["iv"])[:64], "ct": str(body["blob"]["ct"])[:8192]}
        token = secrets.token_urlsafe(24)
        now = time.time()
        with self.store.cond:
            self.store.pairs = {k: p for k, p in self.store.pairs.items() if p["exp"] > now - 600}
            self.store.pairs[token] = {"uid": uid, "blob": blob, "exp": now + PAIR_SECONDS, "device": None}
        self.send_json({"token": token, "ttl": PAIR_SECONDS})

    def handle_pair_claim(self, body):
        store = self.store
        with store.cond:
            pair_info = store.pairs.get(str(body["token"]))
            if not pair_info or pair_info["device"] or pair_info["exp"] < time.time():
                return self.send_json({"error": "Mã kết nối đã hết hạn hoặc đã được dùng. Hãy tạo mã mới trên máy tính"}, 410)
            pair_info["device"] = self.device_name()
            user = store.users[pair_info["uid"]]
        self.session(user, {"blob": pair_info["blob"]})

    def handle_pair_status(self, query):
        uid = self.current_user()
        pair_info = self.store.pairs.get(query.get("token", [""])[0])
        if not uid or not pair_info or pair_info["uid"] != uid:
            return self.send_json({"error": "Không tìm thấy mã kết nối"}, 404)
        self.send_json({"device": pair_info["device"], "left": max(0, int(pair_info["exp"] - time.time()))})

    def handle_ack(self, body):
        """Máy nhận báo đã nhận và giải mã xong tới tin số seq; máy chủ báo lại cho máy gửi."""
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        seq = int(body["seq"])
        with self.store.cond:
            if seq > self.store.delivered.get(uid, 0):
                self.store.delivered[uid] = min(seq, self.store.seq)
                self.store.rseq += 1
                self.store.save()
                self.store.cond.notify_all()
        self.send_json({"ok": True})

    def handle_vault_get(self):
        """Kho dữ liệu riêng của tài khoản (chữ ký, lịch sử ký...), đã mã hóa bằng khóa của chính tài khoản."""
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        user = self.store.users[uid]
        self.send_json({"env": user.get("vault"), "ver": user.get("vaultVer", 0)})

    def handle_vault_put(self, body):
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        env = body["env"]
        if not isinstance(env, dict) or str(uid) not in env.get("keys", {}):
            return self.send_json({"error": "Dữ liệu không hợp lệ"}, 400)
        with self.store.cond:
            user = self.store.users[uid]
            user["vault"] = env
            # Số phiên bản tăng mỗi lần lưu; máy khác của cùng tài khoản thấy số mới trong /api/sync thì tải lại
            user["vaultVer"] = user.get("vaultVer", 0) + 1
            self.store.rseq += 1  # đánh thức các máy đang chờ đồng bộ
            self.store.save()
            self.store.cond.notify_all()
            ver = user["vaultVer"]
        self.send_json({"ok": True, "ver": ver})

    def handle_logout(self, body):
        key = hashlib.sha256(self.headers.get("X-Token", "").encode()).hexdigest()
        with self.store.cond:
            session = self.store.sessions.pop(key, None)
            if session:
                self.store.last_seen.pop(session[0], None)
                self.store.save()
        self.send_json({"ok": True})

    def handle_friend_scan(self, body):
        """Quét mã QR là gửi lời mời kết bạn; người được quét phải đồng ý. Nếu họ đã mời mình trước thì thành bạn bè luôn."""
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        store = self.store
        with store.cond:
            other = next((u for u in store.users.values() if u.get("code") == body["code"]), None)
            if not other:
                return self.send_json({"error": "Mã QR không đúng hoặc đã được đổi"}, 404)
            if other["id"] == uid:
                return self.send_json({"error": "Đây là mã QR của chính bạn"}, 400)
            if body.get("confirm") and pair(uid, other["id"]) not in store.friends:
                if (other["id"], uid) in store.requests:
                    store.requests.discard((other["id"], uid))
                    store.friends.add(pair(uid, other["id"]))
                else:
                    store.requests.add((uid, other["id"]))
                store.bump()
            self.send_json({"id": other["id"], "name": other["name"], "relation": store.relation(uid, other["id"])})

    def handle_friend_code(self, body):
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        with self.store.cond:
            self.store.users[uid]["code"] = secrets.token_urlsafe(12)
            self.store.save()
            self.send_json({"code": self.store.users[uid]["code"]})

    def handle_users(self, query):
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        text = clean_name(query.get("q", [""])[0]).lower()
        store = self.store
        with store.cond:
            # Tìm theo tên, hoặc theo mã số tài khoản (gõ 1001 hoặc #1001)
            num = text.lstrip("#")
            found = [u for u in store.users.values() if u["id"] != uid and (text in u["name"].lower() or (num.isdigit() and num == str(u["id"])))]
            data = [{**brief_user(store, u["id"]), "relation": store.relation(uid, u["id"])} for u in found[:30]]
        self.send_json({"users": data})

    def handle_friend(self, body):
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        other, action = body["id"], body["action"]
        store = self.store
        with store.cond:
            if other == uid or other not in store.users:
                return self.send_json({"error": "Không tìm thấy tài khoản này"}, 404)
            if action == "request":
                if (other, uid) in store.requests:
                    action = "accept"
                elif pair(uid, other) not in store.friends:
                    store.requests.add((uid, other))
            if action == "accept":
                if (other, uid) not in store.requests:
                    return self.send_json({"error": "Lời mời này không còn nữa"}, 404)
                store.requests.discard((other, uid))
                store.friends.add(pair(uid, other))
            elif action == "decline":
                store.requests.discard((other, uid))
            elif action == "cancel":
                store.requests.discard((uid, other))
            elif action == "remove":
                store.friends.discard(pair(uid, other))
            elif action != "request":
                return self.send_json({"error": "Thao tác không hợp lệ"}, 400)
            store.bump()
            self.send_json({"relation": store.relation(uid, other)})

    def handle_sync(self, query):
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        since = int(query.get("since", ["0"])[0])
        rsince = int(query.get("rsince", ["-1"])[0])
        wait = query.get("wait", ["1"])[0] == "1"
        store = self.store
        store.last_seen[uid] = time.time()
        with store.cond:
            if wait:
                store.cond.wait_for(lambda: store.seq > since or store.rseq > rsince, timeout=20)
            store.last_seen[uid] = time.time()
            my_groups = [g for g in store.groups.values() if uid in g["members"]]
            group_ids = {g["id"] for g in my_groups}
            messages = [m for m in store.messages if m["seq"] > since
                        and (m["from"] == uid or m.get("to") == uid or m.get("group") in group_ids)
                        and str(uid) in m["env"]["keys"]]
            friends = store.friends_of(uid)
            # Danh bạ theo tài khoản: bạn bè và người cùng nhóm (cần khóa công khai để mã hóa cho họ)
            people = friends | {m for g in my_groups for m in g["members"] if m != uid}
            pending = {f for f, t in store.requests if t == uid} | {t for f, t in store.requests if f == uid}
            others = [i for i in store.users if i != uid and i not in friends and i not in pending]
            others.sort(key=lambda i: (-len(friends & store.friends_of(i)), store.users[i]["name"].lower()))
            data = {"seq": store.seq, "rseq": store.rseq, "groups": my_groups, "messages": messages, "total": len(store.users),
                    "vault": store.users[uid].get("vaultVer", 0),
                    "receipts": {i: store.delivered.get(i, 0) for i in people},
                    "users": [{**public_user(store, store.users[i]), "friend": i in friends} for i in people],
                    "incoming": [brief_user(store, f) for f, t in store.requests if t == uid],
                    "outgoing": [brief_user(store, t) for f, t in store.requests if f == uid],
                    "suggestions": [{**brief_user(store, i), "mutual": len(friends & store.friends_of(i))} for i in others[:8]]}
        self.send_json(data)

    def handle_send(self, body):
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        store = self.store
        with store.cond:
            to, group = body.get("to"), body.get("group")
            if group is not None:
                allowed = group in store.groups and uid in store.groups[group]["members"]
            else:
                allowed = pair(uid, to) in store.friends
            if not allowed:
                return self.send_json({"error": "Hai bạn cần kết bạn trước khi nhắn tin"}, 403)
            mid = str(body.get("mid", ""))[:64]
            if mid and (uid, mid) in store.recent_mids:
                return self.send_json({"ok": True, "seq": store.recent_mids[(uid, mid)], "duplicate": True})
            store.seq += 1
            msg = {"seq": store.seq, "from": uid, "fromName": store.users[uid]["name"], "ts": int(time.time() * 1000), "env": body["env"]}
            msg.update({"group": group} if group is not None else {"to": to})
            store.messages.append(msg)
            if mid:
                store.recent_mids[(uid, mid)] = msg["seq"]
                if len(store.recent_mids) > 5000:
                    store.recent_mids.pop(next(iter(store.recent_mids)))
            store.save()
            store.cond.notify_all()
        self.send_json({"ok": True, "seq": msg["seq"]})

    def handle_group(self, body):
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        name = clean_name(body["name"])
        store = self.store
        with store.cond:
            friends = store.friends_of(uid)
            members = sorted({uid, *[m for m in body["members"] if m in friends]})
            if not 1 <= len(name) <= 60 or not 3 <= len(members) <= MAX_GROUP:
                return self.send_json({"error": f"Nhóm cần có tên và từ 3 đến {MAX_GROUP} thành viên"}, 400)
            gid = max(store.groups, default=500000) + 1
            store.groups[gid] = {"id": gid, "name": name, "members": members}
            store.bump()
        self.send_json(store.groups[gid])

    def handle_group_add(self, body):
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        store = self.store
        with store.cond:
            group = store.groups.get(body["group"])
            if not group or uid not in group["members"]:
                return self.send_json({"error": "Bạn không ở trong nhóm này"}, 403)
            new = [m for m in body["members"] if m in store.friends_of(uid) and m not in group["members"]]
            if not new or len(group["members"]) + len(new) > MAX_GROUP:
                return self.send_json({"error": f"Hãy chọn bạn bè chưa ở trong nhóm, tối đa {MAX_GROUP} người"}, 400)
            group["members"] = sorted({*group["members"], *new})
            store.bump()
        self.send_json({"ok": True})

    def handle_group_leave(self, body):
        uid = self.current_user()
        if not uid:
            return self.send_json({"error": "Phiên đăng nhập đã hết hạn"}, 401)
        store = self.store
        with store.cond:
            group = store.groups.get(body["group"])
            if not group or uid not in group["members"]:
                return self.send_json({"error": "Bạn không ở trong nhóm này"}, 403)
            group["members"].remove(uid)
            if not group["members"]:
                del store.groups[group["id"]]
            store.bump()
        self.send_json({"ok": True})


class Server(ThreadingHTTPServer):
    # Trên Windows, cho dùng lại địa chỉ nghĩa là hai máy chủ cùng nghe một cổng; giữ cổng độc quyền
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def handle_error(self, request, client_address):
        # Trình duyệt đóng tab giữa chừng là chuyện bình thường, không cần báo lỗi
        if not isinstance(sys.exc_info()[1], (ConnectionError, ssl.SSLError, TimeoutError)):
            super().handle_error(request, client_address)


def public_url():
    """Địa chỉ Internet của máy chủ: biến LANCHAT_PUBLIC_URL (tên miền cố định), hoặc file do chia_se_internet.py ghi."""
    url = os.environ.get("LANCHAT_PUBLIC_URL", "").strip()
    if not url and os.path.exists(PUBLIC_URL_FILE):
        with open(PUBLIC_URL_FILE, encoding="utf-8") as f:
            url = f.read().strip()
    return url.rstrip("/") or None


def server_id():
    """Mã cố định của máy chủ, để app biết các địa chỉ khác nhau cùng trỏ về một máy chủ."""
    if not os.path.exists(SERVER_ID_FILE):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SERVER_ID_FILE, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(8))
    with open(SERVER_ID_FILE, encoding="utf-8") as f:
        return f.read().strip()


def origin_allowed(origin):
    if not origin:
        return False
    own = {f"https://{ip}:{PORT}" for ip in local_ips()} | {f"http://localhost:{LOCAL_PORT}", f"http://127.0.0.1:{LOCAL_PORT}"}
    pub = public_url()
    if pub:
        own.add(pub)
    return origin in ALLOWED_ORIGINS or origin in own


def primary_ip():
    """Địa chỉ của card mạng đang dùng thật. Không có gói tin nào được gửi đi."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def local_ips():
    ips = {"127.0.0.1", primary_ip()}
    try:
        ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return sorted(ips)


def ensure_certificate():
    """Trình duyệt chỉ bật mật mã (crypto.subtle) trên HTTPS khi truy cập qua IP.
    Chứng chỉ gốc riêng của máy chủ chỉ có hiệu lực trong mạng nội bộ, cài một lần trên mỗi máy.
    Chứng chỉ máy chủ được cấp lại khi địa chỉ IP thay đổi."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc)
    day = datetime.timedelta(days=1)
    host = socket.gethostname().lower()
    ips = local_ips()

    def write_key(path, key):
        with open(path, "wb") as f:
            f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))

    if os.path.exists(CA_CERT_PATH) and os.path.exists(CA_KEY_PATH):
        with open(CA_CERT_PATH, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())
        with open(CA_KEY_PATH, "rb") as f:
            ca_key = serialization.load_pem_private_key(f.read(), password=None)
    else:
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"LAN Chat Local CA {secrets.token_hex(3)}")])
        # Giới hạn phạm vi: nếu khóa bị lộ cũng không giả mạo được website trên Internet
        permitted = [x509.DNSName("localhost"), x509.DNSName(host)] + [
            x509.IPAddress(ipaddress.ip_network(n)) for n in ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
        ca_cert = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
                   .serial_number(x509.random_serial_number())
                   .not_valid_before(now - day).not_valid_after(now + 3650 * day)
                   .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                   .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
                   .add_extension(x509.NameConstraints(permitted, None), critical=True)
                   .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
                   .sign(ca_key, hashes.SHA256()))
        write_key(CA_KEY_PATH, ca_key)
        with open(CA_CERT_PATH, "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    if os.path.exists(CERT_PATH) and os.path.exists(KEY_PATH):
        with open(CERT_PATH, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        covered = {str(ip) for ip in names.get_values_for_type(x509.IPAddress)}
        if cert.issuer == ca_cert.subject and covered >= set(ips) and cert.not_valid_after_utc > now + 30 * day:
            return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    alt_names = [x509.DNSName("localhost"), x509.DNSName(host)] + [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "LAN Chat Server")]))
            .issuer_name(ca_cert.subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - day).not_valid_after(now + 397 * day)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    write_key(KEY_PATH, key)
    with open(CERT_PATH, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


def log(line):
    """Ghi ra cửa sổ nếu có, và luôn ghi vào data/server.log để xem lại khi máy chủ chạy ngầm."""
    print(line, flush=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "server.log"), "a", encoding="utf-8") as f:
        print(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {line}", file=f)


def main():
    ensure_certificate()
    Handler.store = Store()
    try:
        # Riêng máy này: trình duyệt tin localhost nên không cần chứng chỉ, và cổng này không mở ra mạng LAN
        local = Server(("127.0.0.1", LOCAL_PORT), Handler)
        server = Server(("0.0.0.0", PORT), Handler)
    except OSError:
        log(f"Không mở được cổng {PORT} hoặc {LOCAL_PORT}: có thể máy chủ đã đang chạy ở cửa sổ khác hoặc chạy ngầm.")
        sys.exit(1)
    threading.Thread(target=local.serve_forever, daemon=True).start()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERT_PATH, KEY_PATH)
    server.socket = context.wrap_socket(server.socket, server_side=True)

    def watch_ip():
        # Máy đổi mạng (đổi Wi‑Fi, IP mới) trong lúc chạy: cấp lại chứng chỉ có IP mới và nạp ngay, không cần khởi động lại
        known = set(local_ips())
        while True:
            time.sleep(15)
            now = set(local_ips())
            if now == known:
                continue
            known = now
            try:
                ensure_certificate()
                context.load_cert_chain(CERT_PATH, KEY_PATH)
                log(f"Địa chỉ mạng đã đổi, đã cấp lại chứng chỉ. Máy khác dùng: https://{primary_ip()}:{PORT}/")
            except Exception as e:
                log(f"Không cấp lại được chứng chỉ khi đổi mạng: {e}")

    threading.Thread(target=watch_ip, daemon=True).start()
    log(f"Máy chủ LAN Chat đang chạy ({len(Handler.store.users)} tài khoản):")
    log(f"  Trên máy này: http://localhost:{LOCAL_PORT}/")
    for ip in local_ips():
        log(f"  https://{ip}:{PORT}/")
    log(f"Cài chứng chỉ gốc một lần trên mỗi máy: https://{primary_ip()}:{PORT}/ca.crt")
    server.serve_forever()


if __name__ == "__main__":
    main()
