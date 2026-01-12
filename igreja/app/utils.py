# app/utils.py
import os
import sys
import math
import importlib.util
import subprocess

def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None

# Drag & Drop (opcional)
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False

# Pillow (imagens)
try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    Image = None
    HAS_PIL = False

def _try_import(name: str) -> bool:
    try:
        import importlib
        importlib.import_module(name)
        return True
    except Exception:
        return False

HAS_RAWPY = _has_module("rawpy") or _try_import("rawpy")          # só importa quando precisa
HAS_FW    = _has_module("faster_whisper") or _try_import("faster_whisper") # idem
HAS_DOCX  = _has_module("docx") or _try_import("docx")           # idem

def create_no_window_flags():
    return subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0

def seconds_to_hms(s):
    try:
        s = float(s)
    except Exception:
        return "00:00:00"
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"

def _ext(p: str) -> str:
    return os.path.splitext(p)[1][1:].lower()

def format_bytes(n):
    try:
        n = float(n)
    except Exception:
        return None
    if n <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = min(int(math.log(n, 1024)), len(units) - 1)
    val = n / (1024 ** i)
    return (f"{val:,.0f}" if val >= 100 else f"{val:,.2f}").replace(",", ".") + f" {units[i]}"