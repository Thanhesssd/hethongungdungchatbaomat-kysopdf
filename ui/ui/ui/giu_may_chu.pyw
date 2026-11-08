"""Giữ máy chủ LAN Chat luôn chạy: tự bật lại sau 5 giây nếu máy chủ bị tắt hoặc gặp lỗi.

Chạy ngầm bằng pythonw (không có cửa sổ). Nhật ký nằm trong data/server.log.
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "server.py")
PYTHON = sys.executable.replace("pythonw.exe", "python.exe")
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW


def main():
    while True:
        result = subprocess.run([PYTHON, SERVER], cwd=HERE, creationflags=NO_WINDOW if os.name == "nt" else 0,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Mã 3: cổng đang bận vì đã có một máy chủ khác chạy, chờ lâu hơn rồi thử lại
        time.sleep(30 if result.returncode == 3 else 5)


if __name__ == "__main__":
    main()
