import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

from app.utils import app_base_dir, load_app_config
from app.version import APP_NAME, APP_VERSION


UPDATE_CONFIG_KEY = "update_manifest_url"
AUTO_UPDATE_CONFIG_KEY = "auto_check_updates"
GITHUB_REPO_CONFIG_KEY = "github_update_repo"
GITHUB_ASSET_NAME_CONFIG_KEY = "github_update_asset_name"
DEFAULT_GITHUB_UPDATE_REPO = "matheussep17/python2"
DEFAULT_GITHUB_UPDATE_ASSET_NAME = f"{APP_NAME}.exe"


class UpdateError(Exception):
    """Erro relacionado ao fluxo de atualizacao."""


def get_update_settings() -> dict:
    config = load_app_config()
    return {
        "manifest_url": str(config.get(UPDATE_CONFIG_KEY, "") or "").strip(),
        "auto_check": bool(config.get(AUTO_UPDATE_CONFIG_KEY, True)),
        "github_repo": str(config.get(GITHUB_REPO_CONFIG_KEY, DEFAULT_GITHUB_UPDATE_REPO) or "").strip(),
        "github_asset_name": str(
            config.get(GITHUB_ASSET_NAME_CONFIG_KEY, DEFAULT_GITHUB_UPDATE_ASSET_NAME) or ""
        ).strip(),
    }


def can_self_update() -> bool:
    return bool(getattr(sys, "frozen", False) and sys.platform.startswith("win"))


def get_current_version() -> str:
    return APP_VERSION


def compare_versions(current: str, remote: str) -> int:
    current_parts = _parse_version(current)
    remote_parts = _parse_version(remote)
    if current_parts < remote_parts:
        return -1
    if current_parts > remote_parts:
        return 1
    return 0


def fetch_update_manifest(timeout: int = 8) -> dict:
    settings = get_update_settings()
    manifest_url = settings["manifest_url"]
    github_repo = settings["github_repo"]
    github_asset_name = settings["github_asset_name"]

    if manifest_url:
        return _fetch_manifest_from_url(manifest_url, timeout)
    if github_repo:
        return _fetch_manifest_from_github_release(github_repo, github_asset_name, timeout)

    raise UpdateError("Nao foi possivel localizar uma configuracao valida para o auto-update.")


def _fetch_manifest_from_url(manifest_url: str, timeout: int) -> dict:
    response = requests.get(manifest_url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise UpdateError("O manifesto de atualizacao nao esta em formato JSON valido.")

    version = str(payload.get("version", "") or "").strip()
    download_url = str(payload.get("url", "") or "").strip()
    notes = str(payload.get("notes", "") or "").strip()
    expected_size = int(payload.get("size", 0) or 0)

    if not version or not download_url:
        raise UpdateError("O manifesto precisa conter 'version' e 'url'.")

    return {
        "version": version,
        "url": download_url,
        "notes": notes,
        "size": expected_size,
        "mandatory": bool(payload.get("mandatory", False)),
    }


def _fetch_manifest_from_github_release(repo: str, asset_name: str, timeout: int) -> dict:
    repo = _normalize_github_repo(repo)
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{APP_NAME}/{APP_VERSION}",
    }

    response = requests.get(api_url, headers=headers, timeout=timeout)
    if response.status_code == 404:
        raise UpdateError(f"Nenhuma release encontrada em '{repo}'.")
    response.raise_for_status()
    payload = response.json()

    tag_name = str(payload.get("tag_name", "") or "").strip()
    version = _normalize_release_version(tag_name)
    notes = str(payload.get("body", "") or "").strip()
    assets = payload.get("assets", []) or []

    selected_asset = None
    for asset in assets:
        if str(asset.get("name", "")).strip().lower() == asset_name.lower():
            selected_asset = asset
            break

    if not selected_asset and assets:
        for asset in assets:
            name = str(asset.get("name", "")).strip().lower()
            if name.endswith(".exe"):
                selected_asset = asset
                break

    if not version:
        raise UpdateError("A release do GitHub precisa ter uma tag de versao, por exemplo 'v1.0.1'.")
    if not selected_asset:
        raise UpdateError(
            f"Nao encontrei o asset '{asset_name}' na release mais recente de '{repo}'."
        )

    download_url = str(selected_asset.get("browser_download_url", "") or "").strip()
    return {
        "version": version,
        "url": download_url,
        "notes": notes,
        "size": int(selected_asset.get("size", 0) or 0),
        "mandatory": False,
        "source": f"github:{repo}",
    }


def has_update(manifest: dict) -> bool:
    return compare_versions(get_current_version(), manifest["version"]) < 0


def download_update_package(manifest: dict, progress_callback=None) -> Path:
    response = requests.get(manifest["url"], stream=True, timeout=20)
    response.raise_for_status()

    total_bytes = int(response.headers.get("content-length", "0") or "0")
    downloaded_bytes = 0
    download_dir = Path(tempfile.mkdtemp(prefix="igreja-update-"))
    package_path = download_dir / f"{APP_NAME}-{manifest['version']}.exe"

    with package_path.open("wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue
            file.write(chunk)
            downloaded_bytes += len(chunk)
            if progress_callback:
                progress_callback(downloaded_bytes, total_bytes)

    expected_size = int(manifest.get("size", 0) or 0)
    if expected_size > 0 and downloaded_bytes != expected_size:
        raise UpdateError(
            "O download da atualizacao ficou incompleto. "
            f"Esperado: {expected_size} bytes. Baixado: {downloaded_bytes} bytes."
        )

    if total_bytes > 0 and downloaded_bytes != total_bytes:
        raise UpdateError(
            "O servidor informou um tamanho diferente do arquivo baixado. "
            f"Esperado: {total_bytes} bytes. Baixado: {downloaded_bytes} bytes."
        )

    if downloaded_bytes <= 0:
        raise UpdateError("O arquivo de atualizacao foi baixado vazio.")

    return package_path


def schedule_windows_self_replace(downloaded_exe: Path) -> None:
    if not can_self_update():
        raise UpdateError("Auto-update disponivel apenas no executavel Windows.")

    current_exe = Path(sys.executable).resolve()
    app_dir = current_exe.parent
    script_path = Path(tempfile.gettempdir()) / f"igreja-update-{os.getpid()}.cmd"
    current_pid = os.getpid()
    source_path = str(downloaded_exe)
    target_path = str(current_exe)
    target_dir = str(app_dir)
    target_new_path = str(current_exe.with_suffix(".new.exe"))
    target_backup_path = str(current_exe.with_suffix(".previous.exe"))

    script = "\n".join(
        [
            "@echo off",
            "setlocal",
            f'set "APP_PID={current_pid}"',
            f'set "SOURCE={source_path}"',
            f'set "TARGET={target_path}"',
            f'set "TARGET_DIR={target_dir}"',
            f'set "TARGET_NEW={target_new_path}"',
            f'set "TARGET_BACKUP={target_backup_path}"',
            ":wait_exit",
            'tasklist /FI "PID eq %APP_PID%" 2>nul | find "%APP_PID%" >nul',
            "if not errorlevel 1 (",
            "  timeout /t 1 /nobreak >nul",
            "  goto wait_exit",
            ")",
            'del /Q "%TARGET_NEW%" >nul 2>&1',
            "for /L %%I in (1,1,90) do (",
            '  copy /Y "%SOURCE%" "%TARGET_NEW%" >nul 2>&1 && goto prepare_swap',
            "  timeout /t 1 /nobreak >nul",
            ")",
            "exit /b 1",
            ":prepare_swap",
            'for %%F in ("%SOURCE%") do set "SOURCE_SIZE=%%~zF"',
            'for %%F in ("%TARGET_NEW%") do set "TARGET_NEW_SIZE=%%~zF"',
            'if not "%SOURCE_SIZE%"=="%TARGET_NEW_SIZE%" exit /b 2',
            'del /Q "%TARGET_BACKUP%" >nul 2>&1',
            'move /Y "%TARGET%" "%TARGET_BACKUP%" >nul 2>&1 || exit /b 3',
            'move /Y "%TARGET_NEW%" "%TARGET%" >nul 2>&1 || (move /Y "%TARGET_BACKUP%" "%TARGET%" >nul 2>&1 & exit /b 4)',
            ":cleanup",
            'del /Q "%SOURCE%" >nul 2>&1',
            'del /Q "%~f0" >nul 2>&1',
        ]
    )
    script_path.write_text(script, encoding="utf-8")

    subprocess.Popen(
        ["cmd.exe", "/c", str(script_path)],
        cwd=str(app_dir),
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _parse_version(value: str) -> tuple[int, ...]:
    parts = []
    for piece in str(value).replace("-", ".").split("."):
        digits = "".join(char for char in piece if char.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def _normalize_release_version(tag_name: str) -> str:
    value = str(tag_name or "").strip()
    if value.lower().startswith("v") and len(value) > 1:
        return value[1:]
    return value


def _normalize_github_repo(value: str) -> str:
    repo = str(value or "").strip()
    match = re.search(r"github\.com[:/]+([^/]+/[^/.]+)", repo, re.IGNORECASE)
    if match:
        repo = match.group(1)
    repo = repo.strip().strip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    return repo
