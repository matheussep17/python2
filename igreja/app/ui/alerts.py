from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk


_ORIGINAL = {}
_APP_ROOT = None
_DIALOG_ACTIVE = False

_LEVELS = {
    "info": {"title": "Informacao", "bootstyle": "info"},
    "success": {"title": "Sucesso", "bootstyle": "success"},
    "warning": {"title": "Aviso", "bootstyle": "warning"},
    "error": {"title": "Erro", "bootstyle": "danger"},
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
        _ORIGINAL["askyesno"] = messagebox.askyesno

    messagebox.showinfo = lambda title=None, message=None, **kw: _proxy("info", title, message, **kw)
    messagebox.showwarning = lambda title=None, message=None, **kw: _proxy("warning", title, message, **kw)
    messagebox.showerror = lambda title=None, message=None, **kw: _proxy("error", title, message, **kw)
    messagebox.askyesno = lambda title=None, message=None, **kw: _confirm_proxy(title, message, **kw)


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


def _confirm_proxy(title, message, **kwargs):
    parent = kwargs.get("parent") or _APP_ROOT
    if parent is None:
        func = _ORIGINAL.get("askyesno", messagebox.askyesno)
        return func(title or "Confirmacao", message or "")
    return ask_yes_no(parent, str(message or ""), str(title or "Confirmacao"))


def show_alert(parent, title: str, message: str, level: str = "info") -> None:
    global _DIALOG_ACTIVE
    level_key = level if level in _LEVELS else "info"
    meta = _LEVELS[level_key]

    try:
        top = parent.winfo_toplevel()
    except Exception:
        top = parent

    mode = getattr(top, "app_theme_mode", "escuro")
    palette = _PALETTE.get(mode, _PALETTE["escuro"])

    try:
        if _DIALOG_ACTIVE:
            return _fallback(level_key, title, message)
        _DIALOG_ACTIVE = True
        dlg = tk.Toplevel(top)
        dlg.title(title or meta["title"])
        dlg.transient(top)
        dlg.resizable(False, False)
        dlg.configure(background=palette["shell"])
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

        shell = tk.Frame(dlg, bg=palette["shell"], padx=1, pady=1, bd=0, highlightthickness=0)
        shell.pack(fill="both", expand=True)

        card = tk.Frame(shell, bg=palette["surface"], padx=18, pady=14, bd=0, highlightthickness=0)
        card.pack(fill="both", expand=True)

        head = tk.Label(
            card,
            text=title or meta["title"],
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

        def _close(_event=None):
            try:
                dlg.destroy()
            except Exception:
                pass
            return "break"

        dlg.bind("<Escape>", _close)
        dlg.bind("<Return>", _close)
        dlg.bind("<KP_Enter>", _close)
        btn.bind("<Return>", _close)
        btn.bind("<KP_Enter>", _close)
        btn.bind("<space>", _close)
        dlg.update_idletasks()
        _center(top, dlg)

        btn.focus_set()
        dlg.grab_set()
        top.wait_window(dlg)
    except Exception:
        _fallback(level_key, title, message)
    finally:
        _DIALOG_ACTIVE = False


def ask_yes_no(parent, message: str, title: str = "Confirmacao") -> bool:
    global _DIALOG_ACTIVE
    try:
        top = parent.winfo_toplevel()
    except Exception:
        top = parent

    mode = getattr(top, "app_theme_mode", "escuro")
    palette = _PALETTE.get(mode, _PALETTE["escuro"])
    result = {"value": False}

    try:
        if _DIALOG_ACTIVE:
            func = _ORIGINAL.get("askyesno", messagebox.askyesno)
            return bool(func(title or "Confirmacao", message or ""))
        _DIALOG_ACTIVE = True
        dlg = tk.Toplevel(top)
        dlg.title(title or "Confirmacao")
        dlg.transient(top)
        dlg.resizable(False, False)
        dlg.configure(background=palette["shell"])

        shell = tk.Frame(dlg, bg=palette["shell"], padx=1, pady=1, bd=0, highlightthickness=0)
        shell.pack(fill="both", expand=True)

        card = tk.Frame(shell, bg=palette["surface"], padx=18, pady=14, bd=0, highlightthickness=0)
        card.pack(fill="both", expand=True)

        head = tk.Label(
            card,
            text=title or "Confirmacao",
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

        btns = tk.Frame(card, bg=palette["surface"], bd=0, highlightthickness=0)
        btns.pack(anchor="e", pady=(2, 0))

        def _set_and_close(value: bool):
            result["value"] = value
            try:
                dlg.destroy()
            except Exception:
                pass
            return "break"

        no_btn = tk.Button(
            btns,
            text="Nao",
            command=lambda: _set_and_close(False),
            bg=palette["shell"],
            fg=palette["title"],
            activebackground=palette["shell"],
            activeforeground=palette["title"],
            relief="flat",
            padx=16,
            pady=6,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        no_btn.pack(side="right")
        yes_btn = tk.Button(
            btns,
            text="Sim",
            command=lambda: _set_and_close(True),
            bg="#16A34A",
            fg="#FFFFFF",
            activebackground="#15803D",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=16,
            pady=6,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        yes_btn.pack(side="right", padx=(0, 8))

        dlg.bind("<Escape>", lambda _e: _set_and_close(False))
        dlg.bind("<Return>", lambda _e: _set_and_close(True))
        dlg.bind("<KP_Enter>", lambda _e: _set_and_close(True))
        dlg.protocol("WM_DELETE_WINDOW", lambda: _set_and_close(False))
        yes_btn.bind("<Return>", lambda _e: _set_and_close(True))
        yes_btn.bind("<KP_Enter>", lambda _e: _set_and_close(True))
        yes_btn.bind("<space>", lambda _e: _set_and_close(True))
        no_btn.bind("<Return>", lambda _e: _set_and_close(False))
        no_btn.bind("<KP_Enter>", lambda _e: _set_and_close(False))
        no_btn.bind("<space>", lambda _e: _set_and_close(False))
        dlg.update_idletasks()
        _center(top, dlg)

        yes_btn.focus_set()
        dlg.grab_set()
        top.wait_window(dlg)
        return bool(result["value"])
    except Exception:
        func = _ORIGINAL.get("askyesno", messagebox.askyesno)
        return bool(func(title or "Confirmacao", message or ""))
    finally:
        _DIALOG_ACTIVE = False


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
