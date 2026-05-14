from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.utils import load_app_config


PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"
AUTO_UPDATE_CONFIG_KEY = "yt_dlp_auto_update"
CHECK_INTERVAL_HOURS_CONFIG_KEY = "yt_dlp_check_interval_hours"
DEFAULT_CHECK_INTERVAL_HOURS = 24


class YtDlpRuntimeError(Exception):
    """Erro relacionado ao runtime atualizavel do yt-dlp."""


def runtime_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "Igreja" / "runtime" / "yt-dlp"
    return Path.home() / ".igreja" / "runtime" / "yt-dlp"


def state_path() -> Path:
    return runtime_root() / "state.json"


def versions_dir() -> Path:
    return runtime_root() / "versions"


def should_auto_update() -> bool:
    config = load_app_config()
    return bool(config.get(AUTO_UPDATE_CONFIG_KEY, True))


def check_interval_seconds() -> int:
    config = load_app_config()
    try:
        hours = float(config.get(CHECK_INTERVAL_HOURS_CONFIG_KEY, DEFAULT_CHECK_INTERVAL_HOURS))
    except (TypeError, ValueError):
        hours = DEFAULT_CHECK_INTERVAL_HOURS
    return int(max(1, hours) * 60 * 60)


def load_state() -> dict:
    path = state_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(data: dict) -> None:
    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    with state_path().open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_installed_versions() -> list[str]:
    root = versions_dir()
    if not root.exists():
        return []

    versions = []
    for child in root.iterdir():
        if child.is_dir() and (child / "yt_dlp" / "__init__.py").exists():
            versions.append(child.name)
    return sorted(versions, key=_parse_version, reverse=True)


def get_external_package_dir(version: str | None = None) -> Path | None:
    selected = version or get_latest_installed_version()
    if not selected:
        return None

    package_dir = versions_dir() / selected
    if (package_dir / "yt_dlp" / "__init__.py").exists():
        return package_dir
    return None


def get_latest_installed_version() -> str | None:
    versions = get_installed_versions()
    return versions[0] if versions else None


def describe_runtime() -> dict:
    external_version = get_latest_installed_version()
    bundled_version = get_bundled_version()
    preferred_external = get_preferred_external_package_dir()
    return {
        "external_version": external_version,
        "bundled_version": bundled_version,
        "active_version": get_loaded_version(),
        "external_path": str(get_external_package_dir(external_version) or ""),
        "preferred_external_path": str(preferred_external or ""),
    }


def get_loaded_version() -> str | None:
    module = sys.modules.get("yt_dlp")
    if not module:
        return None
    return _module_version(module)


def get_bundled_version() -> str | None:
    package_dir = get_external_package_dir()
    removed_external = False
    if package_dir and str(package_dir) in sys.path:
        sys.path.remove(str(package_dir))
        removed_external = True

    previous_modules = _pop_yt_dlp_modules()
    try:
        module = importlib.import_module("yt_dlp")
        return _module_version(module)
    except Exception:
        return None
    finally:
        _pop_yt_dlp_modules()
        sys.modules.update(previous_modules)
        if removed_external:
            sys.path.insert(0, str(package_dir))


def load_yt_dlp(prefer_external: bool = True):
    package_dir = get_preferred_external_package_dir() if prefer_external else None
    if package_dir:
        package_path = str(package_dir)
        if sys.path[:1] != [package_path]:
            try:
                sys.path.remove(package_path)
            except ValueError:
                pass
            sys.path.insert(0, package_path)
        _pop_yt_dlp_modules()

    return importlib.import_module("yt_dlp")


def get_preferred_external_package_dir() -> Path | None:
    external_version = get_latest_installed_version()
    package_dir = get_external_package_dir(external_version)
    if not package_dir:
        return None

    bundled_version = get_bundled_version()
    if bundled_version and _parse_version(external_version) < _parse_version(bundled_version):
        return None
    return package_dir


def maybe_update_yt_dlp(progress_callback=None) -> dict:
    if not should_auto_update():
        return {"updated": False, "skipped": True, "reason": "auto_update_disabled"}

    state = load_state()
    now = time.time()
    last_check = float(state.get("last_check", 0) or 0)
    if now - last_check < check_interval_seconds():
        return {"updated": False, "skipped": True, "reason": "recent_check"}

    try:
        result = update_yt_dlp(progress_callback=progress_callback)
        state = load_state()
        state["last_check"] = now
        state["last_error"] = ""
        save_state(state)
        return result
    except Exception as exc:
        state = load_state()
        state["last_check"] = now
        state["last_error"] = str(exc)
        save_state(state)
        raise


def update_yt_dlp(progress_callback=None) -> dict:
    metadata = fetch_latest_metadata()
    latest_version = metadata["version"]
    installed_version = get_latest_installed_version()

    if installed_version and _parse_version(installed_version) >= _parse_version(latest_version):
        return {
            "updated": False,
            "version": installed_version,
            "latest_version": latest_version,
            "path": str(get_external_package_dir(installed_version) or ""),
        }

    package_dir = _download_and_extract(metadata, progress_callback=progress_callback)
    state = load_state()
    state.update(
        {
            "installed_version": latest_version,
            "last_update": time.time(),
            "last_error": "",
        }
    )
    save_state(state)

    return {
        "updated": True,
        "version": latest_version,
        "latest_version": latest_version,
        "path": str(package_dir),
    }


def fetch_latest_metadata(timeout: int = 12) -> dict:
    response = requests.get(PYPI_URL, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    version = str(payload.get("info", {}).get("version", "") or "").strip()
    files = payload.get("releases", {}).get(version, []) or []
    wheel = None
    for item in files:
        filename = str(item.get("filename", "") or "")
        packagetype = str(item.get("packagetype", "") or "")
        if packagetype == "bdist_wheel" and filename.endswith(".whl"):
            wheel = item
            break

    if not version or not wheel:
        raise YtDlpRuntimeError("Nao encontrei um wheel valido do yt-dlp no PyPI.")

    url = str(wheel.get("url", "") or "").strip()
    if not _is_https_url(url):
        raise YtDlpRuntimeError("A URL do pacote yt-dlp retornada pelo PyPI nao e HTTPS.")

    return {
        "version": version,
        "url": url,
        "filename": str(wheel.get("filename", "") or "yt-dlp.whl"),
        "size": int(wheel.get("size", 0) or 0),
    }


def _download_and_extract(metadata: dict, progress_callback=None) -> Path:
    version = metadata["version"]
    target_dir = versions_dir() / version
    if (target_dir / "yt_dlp" / "__init__.py").exists():
        return target_dir

    temp_dir = Path(tempfile.mkdtemp(prefix="igreja-ytdlp-"))
    wheel_path = temp_dir / metadata["filename"]
    extract_dir = temp_dir / "extract"

    try:
        response = requests.get(metadata["url"], stream=True, timeout=30)
        response.raise_for_status()

        total_bytes = int(response.headers.get("content-length", "0") or "0")
        downloaded = 0
        with wheel_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                file.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_bytes)

        expected_size = int(metadata.get("size", 0) or 0)
        if expected_size > 0 and downloaded != expected_size:
            raise YtDlpRuntimeError("O download do yt-dlp ficou incompleto.")

        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(wheel_path) as archive:
            members = [
                name
                for name in archive.namelist()
                if name.startswith("yt_dlp/") or ".dist-info/" in name
            ]
            if "yt_dlp/__init__.py" not in members:
                raise YtDlpRuntimeError("O pacote baixado nao contem yt_dlp.")
            archive.extractall(extract_dir, members)

        versions_dir().mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(extract_dir), str(target_dir))
        _cleanup_old_versions(keep_version=version)
        return target_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _cleanup_old_versions(keep_version: str) -> None:
    for version in get_installed_versions():
        if version == keep_version:
            continue
        path = versions_dir() / version
        shutil.rmtree(path, ignore_errors=True)


def _module_version(module) -> str | None:
    for attr in ("version", "__version__"):
        value = getattr(module, attr, None)
        if isinstance(value, str) and value:
            return str(value)

    version_module = getattr(module, "version", None)
    value = getattr(version_module, "__version__", None)
    return str(value) if value else None


def _pop_yt_dlp_modules() -> dict:
    removed = {}
    for name in list(sys.modules):
        if name == "yt_dlp" or name.startswith("yt_dlp."):
            removed[name] = sys.modules.pop(name)
    return removed


def _parse_version(value: str | None) -> tuple[int, ...]:
    parts = []
    for piece in str(value or "").replace("-", ".").split("."):
        digits = "".join(char for char in piece if char.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)
