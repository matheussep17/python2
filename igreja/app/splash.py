"""Tela de abertura leve, carregada antes dos módulos pesados do aplicativo."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class SplashScreen:
    """Janela pequena e independente para tornar a inicialização perceptível."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg="#0A0C10")
        self.root.resizable(False, False)

        width, height = 520, 300
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        shell = tk.Frame(self.root, bg="#11141A", highlightthickness=1, highlightbackground="#2A313B")
        shell.pack(fill="both", expand=True)

        canvas = tk.Canvas(shell, width=74, height=74, bg="#11141A", highlightthickness=0)
        canvas.pack(pady=(38, 12))
        canvas.create_oval(7, 7, 67, 67, fill="#202733", outline="#7EA7D8", width=2)
        canvas.create_text(37, 37, text="I", fill="#F4F8FF", font=("Bahnschrift", 34, "bold"))

        tk.Label(
            shell,
            text="MEDIA SUITE",
            bg="#11141A",
            fg="#7EA7D8",
            font=("Bahnschrift", 10, "bold"),
        ).pack()
        tk.Label(
            shell,
            text="Igreja",
            bg="#11141A",
            fg="#F4F8FF",
            font=("Bahnschrift SemiBold", 24),
        ).pack(pady=(2, 12))

        self.status_var = tk.StringVar(value="Preparando o aplicativo...")
        tk.Label(
            shell,
            textvariable=self.status_var,
            bg="#11141A",
            fg="#98A3B2",
            font=("Segoe UI", 10),
        ).pack()

        progress = ttk.Progressbar(shell, mode="indeterminate", length=250)
        progress.pack(pady=(12, 0))
        progress.start(14)
        self.root.update_idletasks()

    def set_status(self, message: str) -> None:
        try:
            self.status_var.set(message)
            self.root.update_idletasks()
        except tk.TclError:
            pass

    def close(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass
