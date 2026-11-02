import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from crypto_utils import CryptoManager
from network_utils import LANServer
from qr_utils import QRManager
from .admin_panel import AdminPanel
from .chat_panel import ChatPanel

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("LAN Secure Messenger")
        self.root.geometry("1000x700")
        self.crypto = CryptoManager()
        self.qr_mgr = QRManager()
        self.server = LANServer(self.crypto)
        self.contacts = {}
        self._setup_ui()
        self._start_network()

    def _setup_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.chat_frame = ttk.Frame(notebook)
        self.contact_frame = ttk.Frame(notebook)
        self.admin_frame = ttk.Frame(notebook)
        notebook.add(self.chat_frame, text="Tin nhắn")
        notebook.add(self.contact_frame, text="Danh bạ")
        notebook.add(self.admin_frame, text="Quản trị")
        self._setup_contact_tab()
        self.chat_panel = ChatPanel(self.chat_frame, self)
        self.admin_panel = AdminPanel(self.admin_frame, self.crypto)

    def _setup_contact_tab(self):
        frame = self.contact_frame
        ttk.Label(frame, text="Danh bạ & Thiết bị", font=("Arial", 12, "bold")).pack(pady=10)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Thêm thủ công", command=self._add_contact_manual).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Quét QR từ ảnh", command=self._add_contact_qr_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Quét QR Camera", command=self._add_contact_qr_cam).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Tạo QR của tôi", command=self._show_my_qr).pack(side=tk.LEFT, padx=2)
        self.contact_tree = ttk.Treeview(frame, columns=("name", "ip", "status", "fp"), show="headings")
        self.contact_tree.heading("name", text="Tên")
        self.contact_tree.heading("ip", text="Địa chỉ IP")
        self.contact_tree.heading("status", text="Trạng thái")
        self.contact_tree.heading("fp", text="Vân tay khóa (SHA-256)")
        self.contact_tree.column("fp", width=250)
        self.contact_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        ttk.Button(frame, text="Mở cuộc trò chuyện", command=self._open_chat).pack(pady=5)

    def _start_network(self):
        self.server.on_message_received = self.chat_panel.on_message_received
        self.server.on_device_found = self._on_device_discovered
        self.server.start()

    def _on_device_discovered(self, addr):
        pass

    def _add_contact_manual(self):
        win = tk.Toplevel(self.root)
        win.title("Thêm liên hệ")
        win.geometry("400x300")
        ttk.Label(win, text="Tên hiển thị:").pack(pady=5)
        name_entry = ttk.Entry(win)
        name_entry.pack(pady=5)
        ttk.Label(win, text="Địa chỉ IP:").pack(pady=5)
        ip_entry = ttk.Entry(win)
        ip_entry.pack(pady=5)
        ttk.Label(win, text="Cổng:").pack(pady=5)
        port_entry = ttk.Entry(win)
        port_entry.insert(0, "54321")
        port_entry.pack(pady=5)
        ttk.Label(win, text="Khóa công khai (PEM):").pack(pady=5)
        pem_text = tk.Text(win, height=8)
        pem_text.pack(pady=5)
        def save_contact():
            name = name_entry.get().strip()
            ip = ip_entry.get().strip()
            port = int(port_entry.get().strip())
            pem = pem_text.get("1.0", tk.END).strip()
            if name and ip and pem:
                self.contacts[name] = {"ip": ip, "port": port, "pem": pem}
                self._refresh_contact_list()
                win.destroy()
        ttk.Button(win, text="Lưu", command=save_contact).pack(pady=5)

    def _add_contact_qr_file(self):
        path = filedialog.askopenfilename(filetypes=[("Ảnh QR", "*.png;*.jpg;*.jpeg")])
        if not path:
            return
        data = self.qr_mgr.decode_qr_image(path)
        if not data:
            messagebox.showerror("Lỗi", "Không đọc được mã QR")
            return
        name = f"Người dùng tại {data['ip']}"
        self.contacts[name] = {"ip": data["ip"], "port": data["port"], "pem": data["public_key"]}
        self._refresh_contact_list()
        messagebox.showinfo("Thành công", "Đã thêm liên hệ")

    def _add_contact_qr_cam(self):
        messagebox.showinfo("Quét QR", "Hướng camera vào mã QR, nhấn Q để thoát")
        data = self.qr_mgr.decode_qr_from_camera()
        if not data:
            return
        name = f"Người dùng tại {data['ip']}"
        self.contacts[name] = {"ip": data["ip"], "port": data["port"], "pem": data["public_key"]}
        self._refresh_contact_list()
        messagebox.showinfo("Thành công", "Đã thêm liên hệ")

    def _show_my_qr(self):
        my_ip = self.server._get_local_ip()
        qr_img = self.qr_mgr.generate_contact_qr(my_ip, 54321, self.crypto.get_public_key_pem())
        qr_img.show(title="Mã QR của tôi")

    def _refresh_contact_list(self):
        for item in self.contact_tree.get_children():
            self.contact_tree.delete(item)
        for name, info in self.contacts.items():
            fp = self.crypto.sha256_hash(info["pem"])[:16] + "..."
            self.contact_tree.insert("", tk.END, values=(name, info["ip"], "Online", fp))

    def _open_chat(self):
        selected = self.contact_tree.selection()
        if not selected:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn một liên hệ")
            return
        item = self.contact_tree.item(selected[0])["values"]
        name = item[0]
        self.chat_panel.set_active_contact(name, self.contacts[name])