import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import os

class AdminPanel:
    def __init__(self, parent, crypto_manager):
        self.parent = parent
        self.crypto = crypto_manager
        self.admin_hash = "6ca13d52ca45cf506126bb9b1691c126f233f18a36f1c4c0f7b3a8a7ad5"
        self.authenticated = False
        self.logs = []
        self._setup_login_ui()

    def _setup_login_ui(self):
        frame = ttk.Frame(self.parent)
        frame.pack(pady=50)
        ttk.Label(frame, text="🔐 Xác thực Quản trị viên", font=("Arial", 14, "bold")).pack(pady=10)
        ttk.Label(frame, text="Mật khẩu Admin:").pack(pady=5)
        self.pass_entry = ttk.Entry(frame, show="*")
        self.pass_entry.pack(pady=5)
        ttk.Button(frame, text="Đăng nhập", command=self._verify_login).pack(pady=10)
        self.info_label = ttk.Label(frame, text="", foreground="red")
        self.info_label.pack(pady=5)

    def _verify_login(self):
        input_hash = self.crypto.sha256_hash(self.pass_entry.get())
        if input_hash == self.admin_hash:
            self.authenticated = True
            for w in self.parent.winfo_children():
                w.destroy()
            self._setup_dashboard()
        else:
            self.info_label.config(text="❌ Sai mật khẩu / Sai Hash")

    def _setup_dashboard(self):
        ttk.Label(self.parent, text="BẢNG QUẢN TRỊ HỆ THỐNG", font=("Arial", 14, "bold")).pack(pady=10)
        ttk.Separator(self.parent, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=5)
        fp = self.crypto.get_key_fingerprint()
        ttk.Label(self.parent, text=f"Vân tay khóa chính: {fp}", font=("Consolas", 9)).pack(pady=5)
        ttk.Label(self.parent, text="Nhật ký Hoạt động & Gói tin:", font=("Arial", 11, "bold")).pack(pady=10)
        self.log_text = tk.Text(self.parent, height=20, wrap=tk.NONE)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        self._add_log("Hệ thống", "Đã khởi tạo cặp khóa RSA-4096 + AES-256-GCM")
        self._add_log("Bảo mật", "SHA-256 đã kích hoạt cho xác thực")
        ttk.Button(self.parent, text="Xem Khóa Công khai", command=self._show_pubkey).pack(pady=5)

    def _add_log(self, category, msg):
        t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{t}] [{category}] → {msg}\n"
        self.log_text.insert(tk.END, line)
        self.log_text.see(tk.END)

    def _show_pubkey(self):
        win = tk.Toplevel(self.parent)
        win.title("Khóa Công khai")
        txt = tk.Text(win, width=80, height=20)
        txt.insert("1.0", self.crypto.get_public_key_pem())
        txt.config(state=tk.DISABLED)
        txt.pack()