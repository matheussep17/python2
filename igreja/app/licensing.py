import hashlib
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from app.utils import load_app_config
from app.version import APP_NAME, APP_VERSION


LICENSE_STATE_FILE = "license_state.json"
DEFAULT_OFFLINE_GRACE_HOURS = 24 * 365 * 20
DEFAULT_TIMEOUT_SECONDS = 10


class LicenseError(Exception):
    pass


class LicenseConnectionError(LicenseError):
    pass


class LicenseValidationError(LicenseError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        normalized = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def to_iso_datetime(value: datetime | None):
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def licensing_storage_dir() -> Path:
    configured_dir = str(os.environ.get("IGREJA_LICENSE_STORAGE_DIR", "") or "").strip()
    if configured_dir:
        return Path(configured_dir)

    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / APP_NAME


def license_state_path() -> Path:
    return licensing_storage_dir() / LICENSE_STATE_FILE


def load_license_settings() -> dict:
    config = load_app_config()
    bypass_devices = config.get("license_bypass_device_fingerprints", [])
    if not isinstance(bypass_devices, list):
        bypass_devices = []
    bypass_machine_names = config.get("license_bypass_machine_names", [])
    if not isinstance(bypass_machine_names, list):
        bypass_machine_names = []
    return {
        "enforced": bool(config.get("license_enforced", False)),
        "api_url": str(config.get("license_api_url", "") or "").strip().rstrip("/"),
        "timeout_seconds": max(3, int(config.get("license_request_timeout_seconds", DEFAULT_TIMEOUT_SECONDS) or DEFAULT_TIMEOUT_SECONDS)),
        "offline_grace_hours": max(1, int(config.get("license_offline_grace_hours", DEFAULT_OFFLINE_GRACE_HOURS) or DEFAULT_OFFLINE_GRACE_HOURS)),
        "bypass_device_fingerprints": [str(item).strip().lower() for item in bypass_devices if str(item).strip()],
        "bypass_machine_names": [str(item).strip().lower() for item in bypass_machine_names if str(item).strip()],
    }


def license_is_enforced(settings: dict | None = None) -> bool:
    return bool((settings or load_license_settings()).get("enforced"))


def device_has_bypass(settings: dict | None = None) -> bool:
    active_settings = settings or load_license_settings()
    current_fingerprint = device_fingerprint().lower()
    if current_fingerprint in set(active_settings.get("bypass_device_fingerprints", [])):
        return True
    current_machine_name = machine_name().strip().lower()
    return current_machine_name in set(active_settings.get("bypass_machine_names", []))


def load_local_license_state() -> dict:
    path = license_state_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_local_license_state(data: dict) -> None:
    target = license_state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def clear_local_license_state() -> None:
    target = license_state_path()
    try:
        target.unlink(missing_ok=True)
    except Exception:
        pass


def machine_name() -> str:
    return (
        os.environ.get("COMPUTERNAME")
        or os.environ.get("HOSTNAME")
        or socket.gethostname()
        or platform.node()
        or "dispositivo"
    )


def _read_windows_machine_guid() -> str:
    if not sys.platform.startswith("win"):
        return ""

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            return str(winreg.QueryValueEx(key, "MachineGuid")[0] or "").strip()
    except Exception:
        return ""


def _read_windows_bios_uuid() -> str:
    if not sys.platform.startswith("win"):
        return ""

    try:
        result = subprocess.run(
            ["wmic", "csproduct", "get", "uuid"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=5,
            check=False,
        )
        lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip() and "uuid" not in line.lower()]
        return lines[0] if lines else ""
    except Exception:
        return ""


def device_fingerprint() -> str:
    raw_parts = [
        APP_NAME,
        machine_name(),
        platform.system(),
        platform.release(),
        platform.machine(),
        _read_windows_machine_guid(),
        _read_windows_bios_uuid(),
        str(uuid.getnode()),
    ]
    raw = "|".join(part.strip() for part in raw_parts if part and str(part).strip())
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def local_license_is_usable_offline(state: dict) -> bool:
    if not state:
        return False
    if state.get("device_fingerprint") != device_fingerprint():
        return False
    if state.get("status") != "active":
        return False

    expires_at = parse_iso_datetime(state.get("expires_at"))
    if expires_at and utcnow() > expires_at:
        return False

    offline_valid_until = parse_iso_datetime(state.get("offline_valid_until"))
    return bool(offline_valid_until and utcnow() <= offline_valid_until)


def describe_license_state(state: dict) -> str:
    if not state:
        return "Nenhuma licença foi ativada neste computador."

    expires_at = parse_iso_datetime(state.get("expires_at"))
    if expires_at:
        expires_label = expires_at.astimezone().strftime("%d/%m/%Y %H:%M")
    else:
        expires_label = "Permanente"

    offline_until = parse_iso_datetime(state.get("offline_valid_until"))
    offline_label = offline_until.astimezone().strftime("%d/%m/%Y %H:%M") if offline_until else "indisponível"
    return (
        f"Login atual: {state.get('username', 'não informado')}\n"
        f"Validade da licença: {expires_label}\n"
        f"Uso offline permitido até: {offline_label}"
    )


def _request_json(url: str, payload: dict, timeout_seconds: int) -> dict:
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=timeout_seconds,
            headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"},
        )
    except requests.RequestException as exc:
        raise LicenseConnectionError(f"Não foi possível conectar ao servidor de licenças.\n\n{exc}") from exc

    try:
        data = response.json()
    except Exception:
        data = {}

    if response.ok:
        return data if isinstance(data, dict) else {}

    message = str(data.get("detail") or data.get("message") or "O servidor rejeitou a licença.")
    raise LicenseValidationError(message)


def activate_with_server(username: str, password: str, settings: dict | None = None) -> dict:
    settings = settings or load_license_settings()
    api_url = settings.get("api_url")
    if not api_url:
        raise LicenseValidationError("Configure 'license_api_url' no config.json antes de exigir licenças.")

    payload = {
        "username": username.strip(),
        "password": password,
        "device_fingerprint": device_fingerprint(),
        "device_name": machine_name(),
        "app_version": APP_VERSION,
    }
    response = _request_json(f"{api_url}/activate", payload, int(settings["timeout_seconds"]))
    state = _build_local_state(response, api_url)
    save_local_license_state(state)
    return state


def validate_with_server(settings: dict | None = None, state: dict | None = None) -> dict:
    settings = settings or load_license_settings()
    current_state = state or load_local_license_state()
    api_url = settings.get("api_url") or current_state.get("server_url", "")
    if not api_url:
        raise LicenseValidationError("Servidor de licenças não configurado.")
    if not current_state:
        raise LicenseValidationError("Nenhuma licença local foi encontrada.")

    payload = {
        "username": current_state.get("username", ""),
        "activation_token": current_state.get("activation_token", ""),
        "device_fingerprint": device_fingerprint(),
        "device_name": machine_name(),
        "app_version": APP_VERSION,
    }
    response = _request_json(f"{api_url}/validate", payload, int(settings["timeout_seconds"]))
    fresh_state = _build_local_state(response, api_url)
    save_local_license_state(fresh_state)
    return fresh_state


def _build_local_state(response: dict, api_url: str) -> dict:
    now = utcnow()
    fallback_offline_until = now + timedelta(hours=DEFAULT_OFFLINE_GRACE_HOURS)
    return {
        "username": response.get("username", ""),
        "license_id": response.get("license_id"),
        "status": response.get("status", "active"),
        "device_fingerprint": response.get("device_fingerprint") or device_fingerprint(),
        "device_name": response.get("device_name") or machine_name(),
        "activation_token": response.get("activation_token", ""),
        "expires_at": response.get("expires_at"),
        "offline_valid_until": response.get("offline_valid_until") or to_iso_datetime(fallback_offline_until),
        "last_validated_at": response.get("validated_at") or to_iso_datetime(now),
        "server_url": api_url,
    }
