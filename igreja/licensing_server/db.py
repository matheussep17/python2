import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "licenses.db"


def utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_db_path() -> Path:
    configured = str(os.environ.get("IGREJA_LICENSE_DB", "") or "").strip()
    return Path(configured) if configured else DEFAULT_DB_PATH


def connect() -> sqlite3.Connection:
    db_path = resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                device_fingerprint TEXT,
                device_name TEXT,
                activation_token TEXT,
                created_at TEXT NOT NULL,
                activated_at TEXT,
                last_validated_at TEXT,
                expires_at TEXT,
                notes TEXT
            )
            """
        )
        conn.commit()


def hash_password(password: str, salt: bytes | None = None) -> str:
    raw_salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=raw_salt, n=2**14, r=8, p=1)
    return f"{raw_salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split("$", 1)
        expected = hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
        return secrets.compare_digest(expected, digest_hex)
    except Exception:
        return False


def fetch_license_by_username(username: str):
    with connect() as conn:
        return conn.execute("SELECT * FROM licenses WHERE username = ?", (username.strip(),)).fetchone()


def create_license(username: str, password: str, expires_at: str | None = None, notes: str = ""):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO licenses (
                username,
                password_hash,
                status,
                created_at,
                expires_at,
                notes
            ) VALUES (?, ?, 'active', ?, ?, ?)
            """,
            (username.strip(), hash_password(password), utcnow_text(), expires_at, notes.strip()),
        )
        conn.commit()


def list_licenses():
    with connect() as conn:
        return conn.execute(
            """
            SELECT
                id, username, status, device_name, device_fingerprint,
                created_at, activated_at, last_validated_at, expires_at, notes
            FROM licenses
            ORDER BY username
            """
        ).fetchall()


def delete_license(username: str):
    with connect() as conn:
        conn.execute("DELETE FROM licenses WHERE username = ?", (username.strip(),))
        conn.commit()


def update_license_binding(username: str, device_fingerprint: str, device_name: str, activation_token: str):
    now = utcnow_text()
    with connect() as conn:
        conn.execute(
            """
            UPDATE licenses
            SET device_fingerprint = ?, device_name = ?, activation_token = ?,
                activated_at = COALESCE(activated_at, ?), last_validated_at = ?
            WHERE username = ?
            """,
            (device_fingerprint, device_name, activation_token, now, now, username.strip()),
        )
        conn.commit()


def touch_license_validation(username: str, device_name: str):
    with connect() as conn:
        conn.execute(
            """
            UPDATE licenses
            SET device_name = ?, last_validated_at = ?
            WHERE username = ?
            """,
            (device_name, utcnow_text(), username.strip()),
        )
        conn.commit()


def update_status(username: str, status: str):
    with connect() as conn:
        conn.execute("UPDATE licenses SET status = ? WHERE username = ?", (status, username.strip()))
        conn.commit()


def reset_device(username: str):
    with connect() as conn:
        conn.execute(
            """
            UPDATE licenses
            SET device_fingerprint = NULL, device_name = NULL, activation_token = NULL, activated_at = NULL
            WHERE username = ?
            """,
            (username.strip(),),
        )
        conn.commit()


def set_expiration(username: str, expires_at: str | None):
    with connect() as conn:
        conn.execute("UPDATE licenses SET expires_at = ? WHERE username = ?", (expires_at, username.strip()))
        conn.commit()
