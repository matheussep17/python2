# app/main.py
import sys
import socket
import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from app.utils import HAS_DND, HAS_FW, HAS_DOCX, TkinterDnD
from app.frames.converter import ConverterFrame
from app.frames.youtube import YouTubeFrame
from app.frames.transcriber import TranscriberFrame

class SuperApp(ttk.Window if not HAS_DND else TkinterDnD.Tk):
    def __init__(self):
        if HAS_DND:
            super().__init__()
            self.title("Mídia Suite — Conversor • YouTube • Transcrição")
            self.style = ttk.Style(theme="darkly")
            self.geometry("1040x620")
        else:
            super().__init__(
                title="Mídia Suite — Conversor • YouTube • Transcrição",
                themename="darkly",
                size=(1040, 620)
            )

        self.minsize(980, 580)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=(16, 12))
        top.grid(row=0, column=0, columnspan=2, sticky="ew")

        ttk.Label(top, text="Mídia Suite", font=("Helvetica", 22, "bold")).pack(side="left")
        self.title_label = ttk.Label(top, text=" — Conversor", font=("Helvetica", 16))
        self.title_label.pack(side="left")

        side = ttk.Frame(self, padding=16)
        side.grid(row=1, column=0, sticky="ns")

        ttk.Button(side, text="⚙️  Conversor", bootstyle=PRIMARY, command=lambda: self._show("converter")).pack(pady=6, fill="x")
        ttk.Button(side, text="⬇️  YouTube", bootstyle=INFO, command=lambda: self._show("youtube")).pack(pady=6, fill="x")

        if HAS_FW and HAS_DOCX:
            ttk.Button(side, text="📝  Transcrição", bootstyle=SUCCESS, command=lambda: self._show("transcribe")).pack(pady=6, fill="x")
        else:
            ttk.Button(side, text="📝  Transcrição (instale deps)", state=DISABLED).pack(pady=6, fill="x")

        self.content = ttk.Frame(self, padding=(6, 16, 16, 16))
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        sb = ttk.Frame(self, padding=(16, 8))
        sb.grid(row=2, column=0, columnspan=2, sticky="ew")

        self.statusbar_var = tk.StringVar(value="Pronto.")
        ttk.Label(sb, textvariable=self.statusbar_var, anchor="w").pack(side="left")

        self.frames = {
            "converter": ConverterFrame(self.content, self._set_status),
            "youtube": YouTubeFrame(self.content, self._set_status),
        }
        if HAS_FW and HAS_DOCX:
            self.frames["transcribe"] = TranscriberFrame(self.content, self._set_status)

        for f in self.frames.values():
            f.grid(row=0, column=0, sticky="nsew")

        self._show("converter")

        self.bind("<Control-Key-1>", lambda e: self._show("converter"))
        self.bind("<Control-Key-2>", lambda e: self._show("youtube"))
        if "transcribe" in self.frames:
            self.bind("<Control-Key-3>", lambda e: self._show("transcribe"))

    def _show(self, key):
        f = self.frames.get(key)
        if not f:
            return
        f.lift()
        self.title_label.config(text={
            "converter": " — Conversor",
            "youtube": " — YouTube",
            "transcribe": " — Transcrição",
        }.get(key, ""))
        self._set_status("Pronto.")

    def _set_status(self, text):
        self.statusbar_var.set(text)

def single_instance_or_exit(port=54321):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
    except OSError:
        try:
            messagebox.showinfo("Já está aberto", "O aplicativo já está em execução.")
        except Exception:
            pass
        sys.exit(0)
    return s

def main():
    _lock = single_instance_or_exit()
    app = SuperApp()
    app.mainloop()

if __name__ == "__main__":
    main()

#python -m app.main
