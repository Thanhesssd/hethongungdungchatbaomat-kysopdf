# Máy chủ LAN cho LAN Chat & Ký số PDF

Máy chủ là chương trình `ui/ui/ui/server.py`. Nó giữ tài khoản, danh sách bạn bè và tin nhắn đã mã hóa, chuyển tin giữa các máy và phục vụ giao diện web. Máy chủ không đọc được nội dung tin nhắn vì khóa giải mã chỉ nằm trên máy người dùng.

## Chọn máy làm máy chủ

| Lựa chọn | Phù hợp | Ghi chú |
|---|---|---|
| Máy tính hoặc laptop sẵn có (Core i3 / Ryzen 3, RAM 4–8 GB, SSD) | Lớp học, nhóm nhỏ, đồ án | Đủ cho vài chục người dùng; máy phải bật trong lúc dùng |
| PC chạy liên tục (Core i5 / Ryzen 5, RAM 16 GB, SSD NVMe) | Văn phòng chạy 24/7 | Nên cắm dây mạng và đặt IP cố định |
| VPS trên Internet | Người dùng ở nhiều mạng, dùng 4G/5G | Có link cố định, không phụ thuộc máy cá nhân |

Hệ điều hành: Windows 10/11 dùng được ngay với các file `.bat` bên dưới. Ubuntu/Debian cũng chạy được bằng `python3 server.py`, cần tự mở cổng 8443 trong tường lửa.

Phần mềm cần có: Python 3.10 trở lên và thư viện `cryptography` (`pip install cryptography`).

## Cài đặt trên Windows (một lần)

Trong thư mục `ui/ui/ui`, bấm đúp `cai-dat-may-chu.bat` và chọn **Yes** khi Windows hỏi quyền. File này:

1. Mở cổng **8443** trong Windows Defender Firewall cho các máy khác trong mạng.
2. Đăng ký tác vụ **LAN Chat Server** trong Task Scheduler để máy chủ tự chạy ngầm mỗi khi đăng nhập Windows và tự khởi động lại nếu bị dừng.
3. Thêm chứng thư gốc của máy chủ vào danh sách tin cậy của máy này, để Chrome không cảnh báo.
4. Bật máy chủ và in địa chỉ cho các máy khác.

Gỡ cài đặt: bấm đúp `go-cai-dat-may-chu.bat`. Tài khoản và tin nhắn trong thư mục `data` được giữ nguyên.

Không muốn cài đặt: bấm đúp `chay-may-chu.bat` mỗi lần cần dùng và giữ cửa sổ đó mở.

## Địa chỉ truy cập

| Thiết bị | Địa chỉ |
|---|---|
| Chính máy chủ | `http://localhost:8000/` |
| Máy khác cùng Wi‑Fi | `https://<IP máy chủ>:8443/`, ví dụ `https://192.168.8.106:8443/` |
| Link GitHub Pages | Bấm **Tự tìm máy chủ** hoặc **Kết nối máy chủ LAN** rồi nhập IP |
| Máy dùng 4G/5G hoặc khác mạng | Chạy `chia-se-internet.bat` (cần `winget install --id Cloudflare.cloudflared`) và dùng link `https://….trycloudflare.com` |

Mỗi máy khác nên cài chứng thư gốc một lần tại `https://<IP máy chủ>:8443/#root-ca` để không bị cảnh báo bảo mật.

## Nên làm thêm

- **IP cố định:** đặt IP tĩnh cho máy chủ trong phần quản trị router (DHCP reservation), để địa chỉ không đổi giữa các ngày. Khi IP đổi, chỉ cần khởi động lại máy chủ: chứng chỉ tự cấp lại cho địa chỉ mới.
- **Sao lưu:** chép thư mục `ui/ui/ui/data` định kỳ. Thư mục này chứa tài khoản, tin nhắn đã mã hóa và khóa của máy chủ, **không đưa lên GitHub hay gửi cho người khác**.
- **Nhật ký:** khi máy chủ chạy ngầm, xem `data/server.log` để biết địa chỉ đang dùng hoặc lỗi khởi động.

## Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Máy khác không mở được `https://IP:8443/` | Kiểm tra chung Wi‑Fi; chạy `cai-dat-may-chu.bat` để mở cổng; Wi‑Fi khách hoặc công cộng có thể chặn các máy nhìn thấy nhau, khi đó dùng điểm phát từ điện thoại |
| Chrome báo `NET::ERR_CERT_AUTHORITY_INVALID` | Cài chứng thư gốc trên máy đó, hoặc chọn Nâng cao, Tiếp tục |
| `data/server.log` báo "Không mở được cổng" | Máy chủ đã chạy ở nơi khác (cửa sổ đen hoặc chạy ngầm); không cần mở thêm |
| App hiện "Mất kết nối máy chủ" | Máy chủ đã tắt hoặc mạng rớt; app tự kết nối lại, hoặc bấm **Kết nối lại** |
