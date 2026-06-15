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
    notes TEXT,
    privacy_deleted_at TEXT,
    privacy_erasure_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_licenses_active_username
ON licenses(username, privacy_deleted_at);
