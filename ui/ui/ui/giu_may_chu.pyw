"""Giữ máy chủ LAN Chat luôn chạy: tự bật lại sau 5 giây nếu máy chủ bị tắt hoặc gặp lỗi.

Nếu máy có cloudflared, giữ luôn đường hầm Internet (chia_se_internet.py): link Internet được ghi vào
may-chu.json trên GitHub, nên điện thoại dùng 4G/5G hoặc mở link GitHub tự kết nối được máy chủ.
Chạy ngầm bằng pythonw (không có cửa sổ). Nhật ký nằm trong data/server.log.
"""
import os
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable.replace("pythonw.exe", "python.exe")
NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW


def keep(script, busy_code=None, pause=5):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    while True:
        result = subprocess.run([PYTHON, os.path.join(HERE, script)], cwd=HERE, creationflags=NO_WINDOW, env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Mã 3: cổng đang bận vì đã có một máy chủ khác chạy, chờ lâu hơn rồi thử lại
        time.sleep(30 if result.returncode == busy_code else pause)


def main():
    if shutil.which("cloudflared") and not os.environ.get("LANCHAT_KHONG_INTERNET"):
        # Chờ máy chủ chạy rồi mới mở đường hầm; đường hầm rớt thì mở lại (link mới tự cập nhật lên GitHub)
        threading.Thread(target=lambda: (time.sleep(8), keep("chia_se_internet.py", pause=15)), daemon=True).start()
    keep("server.py", busy_code=3)


if __name__ == "__main__":
    main()
