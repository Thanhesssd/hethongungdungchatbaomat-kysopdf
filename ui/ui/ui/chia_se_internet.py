"""Chia sẻ máy chủ LAN Chat ra Internet bằng Cloudflare Tunnel.

Không có tên miền: tạo link tạm xxxx.trycloudflare.com (đổi mỗi lần chạy).
Có tên miền đã cấu hình Named Tunnel: đặt LANCHAT_TUNNEL=<tên đường hầm> và LANCHAT_PUBLIC_URL=https://<tên miền>.
Link được ghi vào data/public_url.txt; máy chủ đưa nó vào mã QR để thiết bị dùng 4G/5G kết nối được.
"""
import os
import re
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("LANCHAT_DATA") or os.path.join(BASE_DIR, "data")
URL_FILE = os.path.join(DATA_DIR, "public_url.txt")
LOCAL_PORT = int(os.environ.get("LANCHAT_LOCAL_PORT", 8000))


def write_url(url):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(URL_FILE, "w", encoding="utf-8") as f:
        f.write(url)
    print(f"\nĐịa chỉ Internet của máy chủ: {url}")
    print("Đã đưa vào mã QR mời và mã QR kết bạn. Giữ cửa sổ này mở trong lúc dùng.\n", flush=True)


def main():
    exe = shutil.which("cloudflared")
    if not exe:
        print("Chưa có cloudflared. Cài một lần bằng lệnh:  winget install --id Cloudflare.cloudflared")
        sys.exit(1)
    tunnel, fixed = os.environ.get("LANCHAT_TUNNEL"), os.environ.get("LANCHAT_PUBLIC_URL")
    if tunnel and fixed:
        write_url(fixed.rstrip("/"))
        cmd = [exe, "tunnel", "run", "--url", f"http://localhost:{LOCAL_PORT}", tunnel]
    else:
        print("Đang tạo link tạm qua Cloudflare (đổi mỗi lần chạy lại)...", flush=True)
        cmd = [exe, "tunnel", "--url", f"http://localhost:{LOCAL_PORT}"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    try:
        for line in proc.stdout:
            found = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if found and not (tunnel and fixed):
                write_url(found.group(0))
            elif "ERR" in line:
                print(line.rstrip(), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        if not (tunnel and fixed) and os.path.exists(URL_FILE):
            os.remove(URL_FILE)
        print("Đã ngừng chia sẻ ra Internet.")


if __name__ == "__main__":
    main()
