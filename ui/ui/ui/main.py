import tkinter as tk
import os
from ui.main_window import MainWindow

if __name__ == "__main__":
    os.makedirs("data/keys", exist_ok=True)
    os.makedirs("data/logs", exist_ok=True)
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()