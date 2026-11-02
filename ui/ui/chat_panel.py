import tkinter as tk
from tkinter import ttk

class ChatPanel:
    def __init__(self, parent, main_app):
        self.parent = parent
        self.main = main_app
        self.active_name = None
        self.active_info = None
        self._setup_ui()

    def _setup_ui(self):
        ttk.Label(self.parent, text="Cửa sổ Trò chuyện", font=("Arial", 12, "bold")).pack(pady=5)
        self.chat_display = tk.Text(self.parent, wrap=tk.WORD, state=tk.DISABLED, height=25)
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        input_frame = ttk.Frame(self.parent)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        self.msg_entry = ttk.Entry(input_frame)
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(input_frame, text="Gửi Mã hóa", command=self._send_message).pack(side=tk.RIGHT)

    def set_active_contact(self, name, info):
        self.active_name = name
        self.active_info = info
        self._append_system_msg(f"Đang trò chuyện với: {name} ({info['ip']})")

    def _send_message(self):
        if not self.active_name:
            return
        text = self.msg_entry.get().strip()
        if not text:
            return
        self.msg_entry.delete(0, tk.END)
        ok, note = self.main.server.send_message(
            self.active_info["ip"],
            self.active_info["port"],
            self.active_info["pem"],
            text
        )
        prefix = "✓" if ok else "✗"
        self._append_message("Tôi", text, f"{prefix} {note}")

    def on_message_received(self, sender_ip, content, verified):
        if verified:
            self._append_message(sender_ip, content, "✓ Đã xác minh & giải mã")
        else:
            self._append_message(sender_ip, content, "⚠ Lỗi")

    def _append_message(self, sender, text, status):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"[{sender}]\n{text}\n  → {status}\n\n")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _append_system_msg(self, text):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"--- Hệ thống: {text} ---\n\n")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)