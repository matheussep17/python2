import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

from app.utils import load_app_config
from app.version import APP_NAME, APP_VERSION


UPDATE_CONFIG_KEY = "update_manifest_url"
AUTO_UPDATE_CONFIG_KEY = "auto_check_updates"
GITHUB_REPO_CONFIG_KEY = "github_update_repo"
GITHUB_ASSET_NAME_CONFIG_KEY = "github_update_asset_name"
DEFAULT_GITHUB_UPDATE_REPO = "matheussep17/python2"
DEFAULT_GITHUB_UPDATE_ASSET_NAME = f"{APP_NAME}.exe"
PYINSTALLER_COOKIE = b"MEI\014\013\012\013\016"
REQUIRED_FROZEN_PACKAGE_MARKERS = (
    (PYINSTALLER_COOKIE, "arquivo one-file do PyInstaller"),
    (b"_tcl_data\\init.tcl", "_tcl_data\\init.tcl"),
    (b"_tcl_data\\msgs\\es_mx.msg", "_tcl_data\\msgs\\es_mx.msg"),
    (b"_tk_data\\tk.tcl", "_tk_data\\tk.tcl"),
    (b"tcl86t.dll", "tcl86t.dll"),
    (b"tk86t.dll", "tk86t.dll"),
    (b"_tkinter.pyd", "_tkinter.pyd"),
)


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
    digest = str(payload.get("digest") or payload.get("sha256") or "").strip()

    if not version or not download_url:
        raise UpdateError("O manifesto precisa conter 'version' e 'url'.")

    return {
        "version": version,
        "url": download_url,
        "notes": notes,
        "size": expected_size,
        "digest": _normalize_sha256_digest(digest),
        "mandatory": bool(payload.get("mandatory", False)),
    }


def _fetch_manifest_from_github_release(repo: str, asset_name: str, timeout: int) -> dict:
    repo = _normalize_github_repo(repo)
    api_url = f"https://api.github.com/repos/{repo}/releases?per_page=30"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{APP_NAME}/{APP_VERSION}",
    }

    response = requests.get(api_url, headers=headers, timeout=timeout)
    if response.status_code == 404:
        raise UpdateError(f"Nenhuma release encontrada em '{repo}'.")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise UpdateError("A resposta de releases do GitHub nao esta no formato esperado.")

    manifests = []
    for release in payload:
        if not isinstance(release, dict):
            continue
        if release.get("draft") or release.get("prerelease"):
            continue
        try:
            manifests.append(_build_github_release_manifest(repo, asset_name, release))
        except UpdateError:
            continue

    if not manifests:
        raise UpdateError(
            f"Nao encontrei uma release valida de '{repo}' com o asset '{asset_name}'."
        )

    return sorted(manifests, key=lambda item: _parse_version(item["version"]), reverse=True)[0]


def _build_github_release_manifest(repo: str, asset_name: str, payload: dict) -> dict:
    tag_name = str(payload.get("tag_name", "") or "").strip()
    version = _normalize_release_version(tag_name)
    notes = str(payload.get("body", "") or "").strip()
    assets = payload.get("assets", []) or []

    selected_asset = _select_release_asset(assets, asset_name)

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
        "digest": _normalize_sha256_digest(str(selected_asset.get("digest", "") or "")),
        "mandatory": False,
        "source": f"github:{repo}",
    }


def _select_release_asset(assets: list, asset_name: str) -> dict | None:
    for asset in assets:
        if str(asset.get("name", "")).strip().lower() == asset_name.lower():
            return asset

    for asset in assets:
        name = str(asset.get("name", "")).strip().lower()
        if name.endswith(".exe"):
            return asset

    return None


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

    expected_digest = str(manifest.get("digest", "") or "").strip().lower()
    if expected_digest:
        downloaded_digest = _sha256_file(package_path)
        if downloaded_digest != expected_digest:
            raise UpdateError(
                "O arquivo de atualizacao baixado nao confere com a assinatura esperada. "
                "Tente novamente em alguns minutos."
            )

    _validate_frozen_update_package(package_path)

    return package_path


def schedule_windows_self_replace(downloaded_exe: Path) -> None:
    if not can_self_update():
        raise UpdateError("Auto-update disponivel apenas no executavel Windows.")

    current_exe = Path(sys.executable).resolve()
    app_dir = current_exe.parent
    staged_exe = _stage_update_exe(downloaded_exe, current_exe)
    script_path = Path(tempfile.gettempdir()) / f"igreja-update-{os.getpid()}.cmd"
    log_path = Path(tempfile.gettempdir()) / f"igreja-update-{os.getpid()}.log"
    current_pid = os.getpid()
    source_path = str(staged_exe)
    target_path = str(current_exe)
    target_image = current_exe.name
    backup_path = str(current_exe.with_suffix(current_exe.suffix + ".old"))
    sleep_command = 'powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 1" >nul 2>&1'

    script = "\n".join(
        [
            "@echo off",
            "setlocal EnableExtensions",
            f'set "APP_PID={current_pid}"',
            f'set "SOURCE={source_path}"',
            f'set "TARGET={target_path}"',
            f'set "TARGET_IMAGE={target_image}"',
            f'set "BACKUP={backup_path}"',
            f'set "LOG={log_path}"',
            'echo [%date% %time%] Iniciando atualizacao. > "%LOG%"',
            'echo SOURCE=%SOURCE% >> "%LOG%"',
            'echo TARGET=%TARGET% >> "%LOG%"',
            ":wait_exit",
            'tasklist /FI "PID eq %APP_PID%" 2>nul | find "%APP_PID%" >nul',
            "if not errorlevel 1 (",
            f"  {sleep_command}",
            "  goto wait_exit",
            ")",
            'echo [%date% %time%] Processo principal encerrado. >> "%LOG%"',
            "for /L %%W in (1,1,180) do (",
            '  tasklist /FI "IMAGENAME eq %TARGET_IMAGE%" 2>nul | find /I "%TARGET_IMAGE%" >nul',
            "  if errorlevel 1 goto no_running_instances",
            f"  {sleep_command}",
            ")",
            'echo [%date% %time%] ERRO: ainda existem instancias do aplicativo abertas. >> "%LOG%"',
            "exit /b 1",
            ":no_running_instances",
            'echo [%date% %time%] Nenhuma outra instancia encontrada. >> "%LOG%"',
            'if not exist "%SOURCE%" (',
            '  echo [%date% %time%] ERRO: arquivo baixado nao encontrado. >> "%LOG%"',
            "  exit /b 1",
            ")",
            'for %%A in ("%SOURCE%") do set "SOURCE_SIZE=%%~zA"',
            'echo SOURCE_SIZE=%SOURCE_SIZE% >> "%LOG%"',
            'attrib -R "%TARGET%" >nul 2>&1',
            'del /Q "%BACKUP%" >nul 2>&1',
            "for /L %%I in (1,1,90) do (",
            '  echo [%date% %time%] Tentativa %%I de substituir o executavel. >> "%LOG%"',
            '  powershell -NoProfile -ExecutionPolicy Bypass -Command "[IO.File]::Copy($env:SOURCE, $env:TARGET, $true)" >> "%LOG%" 2>&1',
            "  if not errorlevel 1 (",
            '    for %%A in ("%TARGET%") do set "TARGET_SIZE=%%~zA"',
            '    call echo TARGET_SIZE=%%TARGET_SIZE%% >> "%LOG%"',
            '    call if "%%TARGET_SIZE%%"=="%SOURCE_SIZE%" goto cleanup',
            '    echo [%date% %time%] ERRO: tamanho final divergente apos copia direta. >> "%LOG%"',
            "  )",
            '  echo [%date% %time%] Copia direta falhou; tentando fluxo com backup. >> "%LOG%"',
            '  move /Y "%TARGET%" "%BACKUP%" >> "%LOG%" 2>&1',
            "  if errorlevel 1 (",
            f"    {sleep_command}",
            "  ) else (",
            '    copy /Y "%SOURCE%" "%TARGET%" >> "%LOG%" 2>&1',
            "    if errorlevel 1 (",
            '      echo [%date% %time%] ERRO: falha ao copiar nova versao; restaurando backup. >> "%LOG%"',
            '      del /Q "%TARGET%" >nul 2>&1',
            '      move /Y "%BACKUP%" "%TARGET%" >> "%LOG%" 2>&1',
            f"      {sleep_command}",
            "    ) else (",
            '      for %%A in ("%TARGET%") do set "TARGET_SIZE=%%~zA"',
            '      call echo TARGET_SIZE=%%TARGET_SIZE%% >> "%LOG%"',
            '      call if "%%TARGET_SIZE%%"=="%SOURCE_SIZE%" goto cleanup',
            '      echo [%date% %time%] ERRO: tamanho final divergente; restaurando backup. >> "%LOG%"',
            '      del /Q "%TARGET%" >nul 2>&1',
            '      move /Y "%BACKUP%" "%TARGET%" >> "%LOG%" 2>&1',
            f"      {sleep_command}",
            "    )",
            "  )",
            f"  {sleep_command}",
            ")",
            'echo [%date% %time%] ERRO: nao foi possivel substituir o executavel. >> "%LOG%"',
            "exit /b 1",
            ":cleanup",
            'echo [%date% %time%] Atualizacao aplicada. >> "%LOG%"',
            'del /Q "%SOURCE%" >nul 2>&1',
            'del /Q "%BACKUP%" >nul 2>&1',
            'start "" "%TARGET%"',
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


def _stage_update_exe(downloaded_exe: Path, current_exe: Path) -> Path:
    downloaded_exe = Path(downloaded_exe).resolve()
    current_exe = Path(current_exe).resolve()
    if not downloaded_exe.exists():
        raise UpdateError("O arquivo de atualizacao baixado nao foi encontrado.")

    staged_exe = current_exe.with_name(f"{current_exe.stem}.update-{os.getpid()}{current_exe.suffix}")
    try:
        if staged_exe.exists():
            staged_exe.unlink()
        shutil.copy2(downloaded_exe, staged_exe)
    except OSError as exc:
        raise UpdateError(
            "Nao consegui preparar a atualizacao na pasta do aplicativo. "
            "Verifique se voce tem permissao de escrita nessa pasta ou execute o app como administrador."
        ) from exc

    try:
        if staged_exe.stat().st_size != downloaded_exe.stat().st_size:
            staged_exe.unlink(missing_ok=True)
            raise UpdateError("A copia local da atualizacao ficou incompleta.")
        _validate_frozen_update_package(staged_exe)
    except OSError as exc:
        raise UpdateError("Nao foi possivel validar a copia local da atualizacao.") from exc

    return staged_exe


def _parse_version(value: str) -> tuple[int, ...]:
    parts = []
    for piece in str(value).replace("-", ".").split("."):
        digits = "".join(char for char in piece if char.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def _normalize_sha256_digest(value: str) -> str:
    digest = str(value or "").strip().lower()
    if digest.startswith("sha256:"):
        digest = digest.split(":", 1)[1].strip()
    if re.fullmatch(r"[0-9a-f]{64}", digest):
        return digest
    return ""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_frozen_update_package(path: Path) -> None:
    missing_markers = _missing_binary_markers(path, REQUIRED_FROZEN_PACKAGE_MARKERS)
    if missing_markers:
        raise UpdateError(
            "O arquivo de atualizacao baixado parece incompleto ou corrompido. "
            "Tente baixar novamente. Marcadores ausentes: "
            + ", ".join(missing_markers)
        )


def _missing_binary_markers(path: Path, markers: tuple[tuple[bytes, str], ...]) -> list[str]:
    found = {label: False for _, label in markers}
    max_marker_size = max(len(marker) for marker, _ in markers)
    tail = b""

    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            block = tail + chunk
            for marker, label in markers:
                if not found[label] and marker in block:
                    found[label] = True
            if all(found.values()):
                return []
            tail = block[-max_marker_size + 1 :]

    return [label for label, was_found in found.items() if not was_found]


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
