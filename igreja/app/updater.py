import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

from app.utils import format_bytes, load_app_config
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


def _ps_single_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


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


def describe_update_manifest(manifest: dict) -> str:
    lines = [
        f"Versao: {manifest.get('version', 'desconhecida')}",
    ]

    size = int(manifest.get("size", 0) or 0)
    if size > 0:
        lines.append(f"Tamanho: {format_bytes(size)}")

    digest = str(manifest.get("digest", "") or "").strip().lower()
    if digest:
        lines.append(f"SHA-256: {digest}")

    source = str(manifest.get("source", "") or "").strip()
    if source:
        lines.append(f"Origem: {source}")

    return "\n".join(lines)


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

    downloaded_exe = Path(downloaded_exe).resolve()
    current_exe = Path(sys.executable).resolve()
    app_dir = current_exe.parent
    script_path = Path(tempfile.gettempdir()) / f"igreja-update-{os.getpid()}.ps1"
    log_path = Path(tempfile.gettempdir()) / f"igreja-update-{os.getpid()}.log"
    current_pid = os.getpid()
    package_path = _ps_single_quote(downloaded_exe)
    package_dir = _ps_single_quote(downloaded_exe.parent)
    target_path = _ps_single_quote(current_exe)
    target_name = _ps_single_quote(current_exe.name)
    target_process_name = _ps_single_quote(current_exe.stem)
    backup_path = _ps_single_quote(current_exe.with_suffix(current_exe.suffix + ".old"))
    log_path_ps = _ps_single_quote(log_path)

    script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"$AppPid = {current_pid}",
            f"$Package = {package_path}",
            f"$PackageDir = {package_dir}",
            f"$Target = {target_path}",
            f"$TargetName = {target_name}",
            f"$TargetProcessName = {target_process_name}",
            f"$Backup = {backup_path}",
            f"$Log = {log_path_ps}",
            "function Write-Log {",
            "  param([string]$Message)",
            "  Add-Content -LiteralPath $Log -Value (\"[{0}] {1}\" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss,ff'), $Message)",
            "}",
            "Write-Log 'Iniciando atualizacao.'",
            "Write-Log (\"PACKAGE={0}\" -f $Package)",
            "Write-Log (\"TARGET={0}\" -f $Target)",
            "Write-Log (\"TARGET_NAME={0}\" -f $TargetName)",
            "while (Get-Process -Id $AppPid -ErrorAction SilentlyContinue) {",
            "  Start-Sleep -Seconds 1",
            "}",
            "Write-Log 'Processo principal encerrado.'",
            "$waitCount = 0",
            "while (Get-Process -Name $TargetProcessName -ErrorAction SilentlyContinue) {",
            "  if ($waitCount -ge 180) {",
            "    Write-Log 'ERRO: ainda existem instancias do aplicativo abertas.'",
            "    exit 1",
            "  }",
            "  $waitCount += 1",
            "  Start-Sleep -Seconds 1",
            "}",
            "Write-Log 'Nenhuma outra instancia encontrada.'",
            "if (-not (Test-Path -LiteralPath $Package)) {",
            "  Write-Log 'ERRO: arquivo baixado nao encontrado.'",
            "  exit 1",
            "}",
            "$packageSize = (Get-Item -LiteralPath $Package).Length",
            "Write-Log (\"PACKAGE_SIZE={0}\" -f $packageSize)",
            "$success = $false",
            "for ($attempt = 1; $attempt -le 90; $attempt++) {",
            "  Write-Log (\"Tentativa {0} de copiar o executavel atualizado.\" -f $attempt)",
            "  try {",
            "    if (Test-Path -LiteralPath $Backup) {",
            "      Remove-Item -LiteralPath $Backup -Force -ErrorAction Stop",
            "    }",
            "    if (Test-Path -LiteralPath $Target) {",
            "      Copy-Item -LiteralPath $Target -Destination $Backup -Force -ErrorAction Stop",
            "    }",
            "    Copy-Item -LiteralPath $Package -Destination $Target -Force -ErrorAction Stop",
            "    $targetSize = (Get-Item -LiteralPath $Target).Length",
            "    Write-Log (\"TARGET_SIZE={0}\" -f $targetSize)",
            "    if ($targetSize -ne $packageSize) {",
            "      throw (\"tamanho final divergente apos copia (esperado {0}, obtido {1}).\" -f $packageSize, $targetSize)",
            "    }",
            "    Write-Log 'Atualizacao aplicada.'",
            "    $success = $true",
            "    break",
            "  } catch {",
            "    Write-Log (\"ERRO: {0}\" -f $_.Exception.Message)",
            "    try {",
            "      if (Test-Path -LiteralPath $Backup) {",
            "        Copy-Item -LiteralPath $Backup -Destination $Target -Force -ErrorAction Stop",
            "      }",
            "    } catch {",
            "      Write-Log (\"Falha ao restaurar backup: {0}\" -f $_.Exception.Message)",
            "    }",
            "    Start-Sleep -Seconds 1",
            "  }",
            "}",
            "if (-not $success) {",
            "  Write-Log 'ERRO: nao foi possivel substituir o executavel.'",
            "  exit 1",
            "}",
            "try {",
            "  if (Test-Path -LiteralPath $Package) {",
            "    Remove-Item -LiteralPath $Package -Force -ErrorAction SilentlyContinue",
            "  }",
            "  if (Test-Path -LiteralPath $PackageDir) {",
            "    Remove-Item -LiteralPath $PackageDir -Recurse -Force -ErrorAction SilentlyContinue",
            "  }",
            "  if (Test-Path -LiteralPath $Backup) {",
            "    Remove-Item -LiteralPath $Backup -Force -ErrorAction SilentlyContinue",
            "  }",
            "} finally {",
            "  Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue",
            "}",
            "Write-Log 'Atualizacao concluida. Abra o aplicativo manualmente para usar a nova versao.'",
        ]
    )
    script_path.write_text(script, encoding="utf-8")

    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
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
