# app/utils.py
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

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

try:
    from pypdf import PdfReader, PdfWriter
    HAS_PYPDF = True
except Exception:
    PdfReader = None
    PdfWriter = None
    HAS_PYPDF = False

try:
    import fitz
    HAS_PYMUPDF = True
except Exception:
    fitz = None
    HAS_PYMUPDF = False

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


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def app_config_path() -> Path:
    return app_base_dir() / "config.json"


def load_app_config() -> dict:
    config_path = app_config_path()
    if not config_path.exists():
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_app_config(data: dict) -> None:
    config_path = app_config_path()
    with config_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def _runtime_bundle_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return app_base_dir()


def _candidate_ffmpeg_dirs():
    runtime_base = _runtime_bundle_dir()
    app_base = app_base_dir()
    seen = set()

    candidates = [
        runtime_base / "ffmpeg",
        runtime_base / "ffmpeg" / "bin",
        runtime_base / "vendor" / "ffmpeg",
        runtime_base / "vendor" / "ffmpeg" / "bin",
        app_base / "ffmpeg",
        app_base / "ffmpeg" / "bin",
        app_base / "vendor" / "ffmpeg",
        app_base / "vendor" / "ffmpeg" / "bin",
    ]

    for candidate in candidates:
        normalized = str(candidate).lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        yield candidate


def _binary_name(tool_name: str) -> str:
    return f"{tool_name}.exe" if sys.platform.startswith("win") else tool_name


def resolve_tool_path(tool_name: str):
    binary_name = _binary_name(tool_name)

    for folder in _candidate_ffmpeg_dirs():
        candidate = folder / binary_name
        if candidate.exists():
            return str(candidate)

    found = shutil.which(tool_name)
    if found:
        return found

    found = shutil.which(binary_name)
    if found:
        return found

    return None


def get_ffmpeg_bin_dir():
    ffmpeg_path = resolve_tool_path("ffmpeg")
    if not ffmpeg_path:
        return None
    return str(Path(ffmpeg_path).resolve().parent)


def configure_runtime_environment():
    ffmpeg_bin = get_ffmpeg_bin_dir()
    if not ffmpeg_bin:
        return {"ffmpeg": None, "ffprobe": None, "ffmpeg_bin": None}

    current_path = os.environ.get("PATH", "")
    path_entries = current_path.split(os.pathsep) if current_path else []
    normalized_entries = {entry.lower() for entry in path_entries if entry}
    if ffmpeg_bin.lower() not in normalized_entries:
        os.environ["PATH"] = ffmpeg_bin if not current_path else ffmpeg_bin + os.pathsep + current_path

    return {
        "ffmpeg": resolve_tool_path("ffmpeg"),
        "ffprobe": resolve_tool_path("ffprobe"),
        "ffmpeg_bin": ffmpeg_bin,
    }


def ffmpeg_cmd(*args):
    ffmpeg_path = resolve_tool_path("ffmpeg") or "ffmpeg"
    return [ffmpeg_path, *args]


def ffprobe_cmd(*args):
    ffprobe_path = resolve_tool_path("ffprobe") or "ffprobe"
    return [ffprobe_path, *args]


def missing_runtime_requirements():
    runtime = configure_runtime_environment()
    missing = []

    if not runtime.get("ffmpeg"):
        missing.append("ffmpeg")
    if not runtime.get("ffprobe"):
        missing.append("ffprobe")

    required_modules = {
        "ttkbootstrap": "ttkbootstrap",
        "yt_dlp": "yt-dlp",
        "PIL": "Pillow",
        "docx": "python-docx",
        "faster_whisper": "faster-whisper",
        "pypdf": "pypdf",
        "fitz": "PyMuPDF",
    }
    for module_name, label in required_modules.items():
        if not _has_module(module_name):
            missing.append(label)

    return missing, runtime


def runtime_requirement_message(missing, runtime=None):
    runtime = runtime or {}
    lines = [
        "O aplicativo nao conseguiu preparar o ambiente necessario para iniciar.",
        "",
        "Itens ausentes: " + ", ".join(missing),
    ]

    ffmpeg_bin = runtime.get("ffmpeg_bin")
    if "ffmpeg" in missing or "ffprobe" in missing:
        expected_dir = app_base_dir() / "vendor" / "ffmpeg" / "bin"
        if ffmpeg_bin:
            lines.append("")
            lines.append(f"FFmpeg localizado em: {ffmpeg_bin}")
        else:
            lines.append("")
            lines.append(f"Coloque ffmpeg.exe e ffprobe.exe em: {expected_dir}")

    lines.append("")
    lines.append("Recompile o executavel depois de ajustar os arquivos necessarios.")
    return "\n".join(lines)

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
