from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk


_ORIGINAL = {}
_APP_ROOT = None

_LEVELS = {
    "info": {"icon": "[i]", "title": "Informacao", "bootstyle": "info"},
    "success": {"icon": "[ok]", "title": "Sucesso", "bootstyle": "success"},
    "warning": {"icon": "[!]", "title": "Aviso", "bootstyle": "warning"},
    "error": {"icon": "[x]", "title": "Erro", "bootstyle": "danger"},
}

_PALETTE = {
    "escuro": {"shell": "#0F172A", "surface": "#111827", "title": "#E5E7EB", "text": "#CBD5E1"},
    "claro": {"shell": "#E2E8F0", "surface": "#FFFFFF", "title": "#0F172A", "text": "#334155"},
}


def install_messagebox_hooks(root) -> None:
    global _APP_ROOT
    _APP_ROOT = root

    if not _ORIGINAL:
        _ORIGINAL["showinfo"] = messagebox.showinfo
        _ORIGINAL["showwarning"] = messagebox.showwarning
        _ORIGINAL["showerror"] = messagebox.showerror

    messagebox.showinfo = lambda title=None, message=None, **kw: _proxy("info", title, message, **kw)
    messagebox.showwarning = lambda title=None, message=None, **kw: _proxy("warning", title, message, **kw)
    messagebox.showerror = lambda title=None, message=None, **kw: _proxy("error", title, message, **kw)


def _proxy(level: str, title, message, **kwargs):
    parent = kwargs.get("parent") or _APP_ROOT
    if parent is None:
        return _fallback(level, title, message)
    show_alert(parent, str(title or ""), str(message or ""), level=level)
    return "ok"


def _fallback(level: str, title, message):
    func_name = {
        "info": "showinfo",
        "success": "showinfo",
        "warning": "showwarning",
        "error": "showerror",
    }.get(level, "showinfo")
    func = _ORIGINAL.get(func_name, messagebox.showinfo)
    return func(title or _LEVELS[level]["title"], message or "")


def show_alert(parent, title: str, message: str, level: str = "info") -> None:
    level_key = level if level in _LEVELS else "info"
    meta = _LEVELS[level_key]

    try:
        top = parent.winfo_toplevel()
    except Exception:
        top = parent

    mode = getattr(top, "app_theme_mode", "escuro")
    palette = _PALETTE.get(mode, _PALETTE["escuro"])

    try:
        dlg = tk.Toplevel(top)
        dlg.title(title or meta["title"])
        dlg.transient(top)
        dlg.resizable(False, False)
        dlg.configure(background=palette["shell"])

        shell = tk.Frame(dlg, bg=palette["shell"], padx=1, pady=1, bd=0, highlightthickness=0)
        shell.pack(fill="both", expand=True)

        card = tk.Frame(shell, bg=palette["surface"], padx=18, pady=14, bd=0, highlightthickness=0)
        card.pack(fill="both", expand=True)

        head = tk.Label(
            card,
            text=f"{meta['icon']} {title or meta['title']}",
            bg=palette["surface"],
            fg=palette["title"],
            font=("Segoe UI", 12, "bold"),
            anchor="w",
            justify="left",
        )
        head.pack(fill="x")

        body = tk.Label(
            card,
            text=message or "Sem detalhes.",
            bg=palette["surface"],
            fg=palette["text"],
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=520,
            pady=10,
        )
        body.pack(fill="x")

        btn = ttk.Button(card, text="Entendi", bootstyle=meta["bootstyle"], command=dlg.destroy)
        btn.pack(anchor="e", pady=(2, 0))

        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        dlg.bind("<Return>", lambda _e: dlg.destroy())
        dlg.update_idletasks()
        _center(top, dlg)

        btn.focus_set()
        dlg.grab_set()
        top.wait_window(dlg)
    except Exception:
        _fallback(level_key, title, message)


def _center(parent, dialog) -> None:
    try:
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        dw = dialog.winfo_reqwidth()
        dh = dialog.winfo_reqheight()
        x = px + max(8, (pw - dw) // 2)
        y = py + max(8, (ph - dh) // 2)
        dialog.geometry(f"+{x}+{y}")
    except Exception:
        pass


def show_info(parent, message: str, title: str = "Informacao") -> None:
    show_alert(parent, title, message, level="info")


def show_success(parent, message: str, title: str = "Sucesso") -> None:
    show_alert(parent, title, message, level="success")


def show_warning(parent, message: str, title: str = "Aviso") -> None:
    show_alert(parent, title, message, level="warning")


def show_error(parent, message: str, title: str = "Erro") -> None:
    show_alert(parent, title, message, level="error")
