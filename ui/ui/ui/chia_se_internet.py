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
    publish_directory(url)


def publish_directory(public):
    """Ghi địa chỉ hiện tại vào may-chu.json rồi đẩy lên GitHub, để app bản GitHub Pages tự kết nối máy chủ này
    trên mọi thiết bị (Wi-Fi, 4G/5G) mà không cần gõ địa chỉ. Tắt bằng biến môi trường LANCHAT_KHONG_DAY_GITHUB=1."""
    import json
    import time
    import urllib.request
    if os.environ.get("LANCHAT_KHONG_DAY_GITHUB"):
        return
    try:
        with urllib.request.urlopen(f"http://localhost:{LOCAL_PORT}/api/health", timeout=5) as r:
            health = json.load(r)
    except Exception:
        health = {}
    data = {"id": health.get("id"), "public": public, "lan": health.get("lan", []), "at": int(time.time())}
    path = os.path.join(BASE_DIR, "may-chu.json")
    # Giữ địa chỉ máy chủ đám mây (nếu đã có): app GitHub ưu tiên máy chủ đó vì nó luôn bật
    try:
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
        for k in ("cloud", "cloudId"):
            if old.get(k):
                data[k] = old[k]
    except (OSError, ValueError):
        pass
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    def git(*args):
        return subprocess.run(["git", *args], cwd=BASE_DIR, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
    try:
        if git("rev-parse", "--is-inside-work-tree").returncode:
            return
        git("add", "may-chu.json")
        if not git("diff", "--cached", "--name-only", "--", "may-chu.json").stdout.strip():
            return print("Địa chỉ trên GitHub đã đúng, không cần cập nhật.", flush=True)
        # Chỉ commit đúng file địa chỉ, không đụng các thay đổi khác đang làm dở
        git("commit", "-m", "Cập nhật địa chỉ máy chủ", "--", "may-chu.json")
        r = git("push", "origin", "HEAD")
        if r.returncode == 0:
            print("✅ Đã cập nhật địa chỉ lên GitHub: thiết bị mở app bản GitHub sẽ tự kết nối sau khoảng 1 phút.", flush=True)
        else:
            print("⚠ Không đẩy được địa chỉ lên GitHub: " + (r.stderr.strip().splitlines() or ["?"])[-1], flush=True)
    except Exception as e:
        print(f"⚠ Không cập nhật được địa chỉ lên GitHub: {e}", flush=True)


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
