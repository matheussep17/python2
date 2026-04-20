# app/utils.py
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import requests


FFMPEG_DOWNLOAD_URL_KEY = "ffmpeg_download_url"
DEFAULT_FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
OUTPUT_FOLDER_KEY = "output_folder"


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


def bundled_app_config_path() -> Path:
    return _runtime_bundle_dir() / "config.json"


def load_app_config() -> dict:
    config_data = {}
    bundled_config_path = bundled_app_config_path()
    if bundled_config_path.exists():
        try:
            with bundled_config_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    config_data.update(data)
        except Exception:
            pass

    config_path = app_config_path()
    if not config_path.exists():
        return config_data

    try:
        with config_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict):
                config_data.update(data)
            return config_data
    except Exception:
        return config_data


def save_app_config(data: dict) -> None:
    config_path = app_config_path()
    with config_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def normalize_folder_path(path_value) -> str:
    try:
        return os.path.abspath(os.path.expanduser(str(path_value))) if path_value else ""
    except Exception:
        return str(path_value or "")


def get_output_folder() -> str:
    config = load_app_config()
    return normalize_folder_path(config.get(OUTPUT_FOLDER_KEY) or config.get("destination_folder", ""))


def save_output_folder(folder: str) -> str:
    normalized = normalize_folder_path(folder)
    config = load_app_config()
    config[OUTPUT_FOLDER_KEY] = normalized
    save_app_config(config)
    return normalized


def get_ffmpeg_download_url() -> str:
    config = load_app_config()
    return str(config.get(FFMPEG_DOWNLOAD_URL_KEY, DEFAULT_FFMPEG_DOWNLOAD_URL) or "").strip()


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


def get_available_js_runtimes() -> dict[str, dict[str, str]]:
    runtimes: dict[str, dict[str, str]] = {}

    node_path = resolve_tool_path("node")
    if node_path:
        runtimes["node"] = {"path": node_path}

    deno_path = resolve_tool_path("deno")
    if deno_path:
        runtimes["deno"] = {"path": deno_path}

    return runtimes


def get_ffmpeg_bin_dir():
    ffmpeg_path = resolve_tool_path("ffmpeg")
    if not ffmpeg_path:
        return None
    return str(Path(ffmpeg_path).resolve().parent)


def ffmpeg_vendor_bin_dir() -> Path:
    return app_base_dir() / "vendor" / "ffmpeg" / "bin"


def download_and_install_ffmpeg(package_url: str | None = None, progress_callback=None) -> Path:
    if not sys.platform.startswith("win"):
        raise RuntimeError("A instalacao automatica do FFmpeg esta disponivel apenas no Windows.")

    package_url = str(package_url or get_ffmpeg_download_url()).strip()
    if not package_url:
        raise RuntimeError("Configure 'ffmpeg_download_url' no config.json para baixar o FFmpeg automaticamente.")

    download_dir = Path(tempfile.mkdtemp(prefix="igreja-ffmpeg-download-"))
    package_path = download_dir / "ffmpeg.zip"
    extract_dir = download_dir / "extract"
    target_dir = ffmpeg_vendor_bin_dir()

    response = requests.get(package_url, stream=True, timeout=30)
    response.raise_for_status()

    total_bytes = int(response.headers.get("content-length", "0") or "0")
    downloaded_bytes = 0

    with package_path.open("wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue
            file.write(chunk)
            downloaded_bytes += len(chunk)
            if progress_callback:
                progress_callback(downloaded_bytes, total_bytes)

    with zipfile.ZipFile(package_path) as archive:
        ffmpeg_member = _find_zip_member(archive, "ffmpeg.exe")
        ffprobe_member = _find_zip_member(archive, "ffprobe.exe")

        if not ffmpeg_member or not ffprobe_member:
            raise RuntimeError("O pacote baixado nao contem ffmpeg.exe e ffprobe.exe.")

        archive.extract(ffmpeg_member, path=extract_dir)
        archive.extract(ffprobe_member, path=extract_dir)

    extracted_ffmpeg = extract_dir / Path(ffmpeg_member)
    extracted_ffprobe = extract_dir / Path(ffprobe_member)

    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(extracted_ffmpeg, target_dir / "ffmpeg.exe")
    shutil.copyfile(extracted_ffprobe, target_dir / "ffprobe.exe")

    return target_dir


def _find_zip_member(archive: zipfile.ZipFile, filename: str) -> str | None:
    expected = filename.lower()
    for member in archive.namelist():
        if member.endswith("/"):
            continue
        if Path(member).name.lower() == expected:
            return member
    return None


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
    config = load_app_config()
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
            if str(config.get(FFMPEG_DOWNLOAD_URL_KEY, "") or "").strip():
                lines.append("Ou configure o download automatico do FFmpeg no primeiro inicio.")

    lines.append("")
    lines.append("Ajuste os arquivos necessarios e abra o aplicativo novamente.")
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
