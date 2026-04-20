import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from licensing_server.db import (
    create_license,
    delete_license,
    fetch_license_by_username,
    init_db,
    list_licenses,
    reset_device,
    set_expiration,
    touch_license_validation,
    update_license_binding,
    update_status,
    verify_password,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(value: str | None):
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


OFFLINE_GRACE_HOURS = max(1, int(os.environ.get("IGREJA_OFFLINE_GRACE_HOURS", str(24 * 365 * 20))))
ADMIN_TOKEN = str(os.environ.get("IGREJA_ADMIN_TOKEN", "") or "").strip()

app = FastAPI(title="Igreja Licensing API", version="1.0.0")
init_db()


class ActivateRequest(BaseModel):
    username: str
    password: str
    device_fingerprint: str
    device_name: str | None = None
    app_version: str | None = None


class ValidateRequest(BaseModel):
    username: str
    activation_token: str
    device_fingerprint: str
    device_name: str | None = None
    app_version: str | None = None


class AdminCreateLicenseRequest(BaseModel):
    username: str
    password: str
    expires_at: str | None = None
    notes: str | None = None


class AdminExpirationRequest(BaseModel):
    expires_at: str | None = None


def _build_license_payload(row) -> dict:
    now = utcnow()
    return {
        "license_id": row["id"],
        "username": row["username"],
        "status": row["status"],
        "device_fingerprint": row["device_fingerprint"],
        "device_name": row["device_name"],
        "activation_token": row["activation_token"],
        "expires_at": row["expires_at"],
        "validated_at": now.isoformat(),
        "offline_valid_until": (now + timedelta(hours=OFFLINE_GRACE_HOURS)).isoformat(),
    }


def _row_to_admin_payload(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "status": row["status"],
        "device_fingerprint": row["device_fingerprint"],
        "device_name": row["device_name"],
        "created_at": row["created_at"],
        "activated_at": row["activated_at"],
        "last_validated_at": row["last_validated_at"],
        "expires_at": row["expires_at"],
        "notes": row["notes"],
    }


def _require_admin_token(token: str | None):
    if not ADMIN_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Configure IGREJA_ADMIN_TOKEN no servidor antes de usar o painel administrativo.",
        )
    if not token or token.strip() != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token administrativo inválido.")


def _ensure_license_is_usable(row):
    if row is None:
        raise HTTPException(status_code=401, detail="Login ou senha inválidos.")

    if row["status"] != "active":
        raise HTTPException(status_code=403, detail="Esta licença está bloqueada.")

    expires_at = parse_iso(row["expires_at"])
    if expires_at and utcnow() > expires_at:
        raise HTTPException(status_code=403, detail="Esta licença expirou e precisa ser renovada.")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/admin", response_class=HTMLResponse)
def admin_panel():
    return """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Painel de Licenças</title>
  <style>
    :root {
      --bg: #0b1320;
      --panel: #111c2d;
      --panel-2: #18263c;
      --text: #eef4ff;
      --muted: #9fb2cf;
      --accent: #67d5b5;
      --danger: #ff7b72;
      --warning: #ffd166;
      --line: #2b3b56;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #08101a 0%, #0f1726 100%);
      color: var(--text);
    }
    .wrap {
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px;
    }
    .hero {
      margin-bottom: 22px;
    }
    .eyebrow {
      color: var(--accent);
      font-size: 12px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }
    h1 {
      margin: 8px 0 6px;
      font-size: 34px;
    }
    .sub {
      color: var(--muted);
      max-width: 800px;
      line-height: 1.5;
    }
    .grid {
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 18px;
      align-items: start;
    }
    .card {
      background: rgba(17, 28, 45, 0.96);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.25);
    }
    .card h2 {
      margin-top: 0;
      font-size: 18px;
    }
    label {
      display: block;
      font-size: 13px;
      margin-bottom: 6px;
      color: var(--muted);
    }
    input, textarea, button, select {
      width: 100%;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--text);
      padding: 10px 12px;
      font: inherit;
    }
    textarea { min-height: 76px; resize: vertical; }
    button {
      cursor: pointer;
      background: #18314f;
      transition: 120ms ease;
    }
    button:hover { filter: brightness(1.08); }
    .primary { background: #1f7a64; }
    .danger { background: #6b2323; }
    .warning { background: #6f5720; }
    .row {
      display: grid;
      gap: 12px;
      margin-bottom: 12px;
    }
    .row.two { grid-template-columns: 1fr 1fr; }
    .toolbar {
      display: flex;
      gap: 10px;
      margin-bottom: 14px;
    }
    .toolbar input { flex: 1; }
    .toolbar button { width: auto; min-width: 150px; }
    .status {
      margin-bottom: 14px;
      min-height: 24px;
      color: var(--muted);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 14px;
    }
    th, td {
      text-align: left;
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      font-size: 14px;
    }
    th { color: var(--muted); font-weight: 600; }
    .tag {
      display: inline-block;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      border: 1px solid var(--line);
      background: #102038;
    }
    .tag.active { color: var(--accent); }
    .tag.revoked { color: var(--danger); }
    .actions {
      display: grid;
      gap: 8px;
    }
    .mini {
      padding: 8px 10px;
      font-size: 13px;
    }
    .mono {
      font-family: Consolas, monospace;
      font-size: 12px;
      color: var(--muted);
      word-break: break-all;
    }
    @media (max-width: 960px) {
      .grid { grid-template-columns: 1fr; }
      .row.two { grid-template-columns: 1fr; }
      .toolbar { flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="eyebrow">Painel Administrativo</div>
      <h1>Gerenciamento de Licenças</h1>
      <div class="sub">
        Crie logins e senhas, veja o computador vinculado, bloqueie, reative, renove validade e libere troca de máquina sem mexer no executável.
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Acesso</h2>
        <div class="row">
          <div>
            <label>Token administrativo</label>
            <input id="adminToken" type="password" placeholder="IGREJA_ADMIN_TOKEN" />
          </div>
        </div>

        <h2>Nova Licença</h2>
        <div class="row">
          <div>
            <label>Login</label>
            <input id="username" placeholder="Ex.: NOTEBOOK-SALA-1" />
          </div>
        </div>
        <div class="row">
          <div>
            <label>Senha</label>
            <input id="password" placeholder="Senha inicial" />
          </div>
        </div>
        <div class="row">
          <div>
            <label>Validade ISO opcional</label>
            <input id="expiresAt" placeholder="2026-12-31T23:59:59+00:00" />
          </div>
        </div>
        <div class="row">
          <div>
            <label>Observações</label>
            <textarea id="notes" placeholder="Sala, responsável, observações internas"></textarea>
          </div>
        </div>
        <div class="row two">
          <button class="primary" onclick="createLicense()">Criar licença</button>
          <button onclick="loadLicenses()">Atualizar lista</button>
        </div>
      </div>

      <div class="card">
        <div class="toolbar">
          <input id="filterInput" placeholder="Filtrar por login, status ou dispositivo" oninput="renderLicenses()" />
          <button onclick="loadLicenses()">Recarregar</button>
        </div>
        <div id="status" class="status">Informe o token administrativo e clique em Recarregar.</div>
        <div style="overflow:auto;">
          <table>
            <thead>
              <tr>
                <th>Login</th>
                <th>Status</th>
                <th>Validade</th>
                <th>Dispositivo</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody id="licensesBody"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <script>
    let licenses = [];

    function adminHeaders() {
      return {
        "Content-Type": "application/json",
        "X-Admin-Token": document.getElementById("adminToken").value.trim()
      };
    }

    function setStatus(message, isError = false) {
      const status = document.getElementById("status");
      status.textContent = message;
      status.style.color = isError ? "#ff7b72" : "#9fb2cf";
    }

    async function apiFetch(url, options = {}) {
      const response = await fetch(url, {
        ...options,
        headers: {
          ...(options.headers || {}),
          ...adminHeaders()
        }
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || data.message || "Falha na operação.");
      }
      return data;
    }

    async function loadLicenses() {
      try {
        setStatus("Carregando licenças...");
        licenses = await apiFetch("/api/v1/admin/licenses");
        renderLicenses();
        setStatus(`Licenças carregadas: ${licenses.length}`);
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    function renderLicenses() {
      const body = document.getElementById("licensesBody");
      const filter = document.getElementById("filterInput").value.trim().toLowerCase();
      const filtered = licenses.filter(item => {
        if (!filter) return true;
        const text = [
          item.username,
          item.status,
          item.device_name || "",
          item.device_fingerprint || "",
          item.notes || ""
        ].join(" ").toLowerCase();
        return text.includes(filter);
      });

      body.innerHTML = filtered.map(item => {
        const expires = item.expires_at || "Permanente";
        const device = item.device_name
          ? `<div>${item.device_name}</div><div class="mono">${item.device_fingerprint || ""}</div>`
          : `<span class="mono">Sem vínculo</span>`;
        return `
          <tr>
            <td>
              <strong>${item.username}</strong>
              <div class="mono">${item.notes || ""}</div>
            </td>
            <td><span class="tag ${item.status}">${item.status}</span></td>
            <td>
              <div>${expires}</div>
              <div class="mono">Criada em ${item.created_at || ""}</div>
            </td>
            <td>${device}</td>
            <td>
              <div class="actions">
                <button class="mini" onclick="reactivateLicense('${item.username}')">Reativar</button>
                <button class="mini warning" onclick="changeExpiration('${item.username}')">Alterar validade</button>
                <button class="mini" onclick="resetDevice('${item.username}')">Resetar dispositivo</button>
                <button class="mini danger" onclick="revokeLicense('${item.username}')">Revogar</button>
                <button class="mini danger" onclick="deleteLicense('${item.username}')">Excluir</button>
              </div>
            </td>
          </tr>
        `;
      }).join("");
    }

    async function createLicense() {
      const payload = {
        username: document.getElementById("username").value.trim(),
        password: document.getElementById("password").value.trim(),
        expires_at: document.getElementById("expiresAt").value.trim() || null,
        notes: document.getElementById("notes").value.trim() || null
      };

      if (!payload.username || !payload.password) {
        setStatus("Login e senha são obrigatórios para criar a licença.", true);
        return;
      }

      try {
        await apiFetch("/api/v1/admin/licenses", {
          method: "POST",
          body: JSON.stringify(payload)
        });
        setStatus(`Licença ${payload.username} criada com sucesso.`);
        document.getElementById("username").value = "";
        document.getElementById("password").value = "";
        document.getElementById("expiresAt").value = "";
        document.getElementById("notes").value = "";
        await loadLicenses();
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function revokeLicense(username) {
      if (!confirm(`Revogar a licença ${username}?`)) return;
      try {
        await apiFetch(`/api/v1/admin/licenses/${encodeURIComponent(username)}/revoke`, { method: "POST" });
        setStatus(`Licença ${username} revogada.`);
        await loadLicenses();
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function reactivateLicense(username) {
      try {
        await apiFetch(`/api/v1/admin/licenses/${encodeURIComponent(username)}/reactivate`, { method: "POST" });
        setStatus(`Licença ${username} reativada.`);
        await loadLicenses();
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function resetDevice(username) {
      if (!confirm(`Liberar ${username} para outro computador?`)) return;
      try {
        await apiFetch(`/api/v1/admin/licenses/${encodeURIComponent(username)}/reset-device`, { method: "POST" });
        setStatus(`Dispositivo de ${username} foi liberado.`);
        await loadLicenses();
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function changeExpiration(username) {
      const value = prompt("Nova validade ISO (deixe vazio para permanente):", "");
      if (value === null) return;
      try {
        await apiFetch(`/api/v1/admin/licenses/${encodeURIComponent(username)}/expiration`, {
          method: "POST",
          body: JSON.stringify({ expires_at: value.trim() || null })
        });
        setStatus(`Validade de ${username} atualizada.`);
        await loadLicenses();
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function deleteLicense(username) {
      if (!confirm(`Excluir definitivamente a licença ${username}?`)) return;
      try {
        await apiFetch(`/api/v1/admin/licenses/${encodeURIComponent(username)}`, { method: "DELETE" });
        setStatus(`Licença ${username} excluída.`);
        await loadLicenses();
      } catch (error) {
        setStatus(error.message, true);
      }
    }
  </script>
</body>
</html>
    """


@app.post("/api/v1/activate")
def activate(payload: ActivateRequest):
    row = fetch_license_by_username(payload.username)
    _ensure_license_is_usable(row)

    if not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Login ou senha inválidos.")

    if row["device_fingerprint"] and row["device_fingerprint"] != payload.device_fingerprint:
        raise HTTPException(
            status_code=409,
            detail="Esta licença já está vinculada a outro computador. Faça a transferência antes de ativar de novo.",
        )

    activation_token = row["activation_token"] or secrets.token_urlsafe(32)
    update_license_binding(
        payload.username,
        payload.device_fingerprint,
        payload.device_name or "dispositivo",
        activation_token,
    )
    fresh = fetch_license_by_username(payload.username)
    return _build_license_payload(fresh)


@app.post("/api/v1/validate")
def validate(payload: ValidateRequest):
    row = fetch_license_by_username(payload.username)
    _ensure_license_is_usable(row)

    if row["activation_token"] != payload.activation_token:
        raise HTTPException(status_code=401, detail="Token de ativação inválido para este login.")

    if row["device_fingerprint"] != payload.device_fingerprint:
        raise HTTPException(status_code=409, detail="Esta licença pertence a outro computador.")

    touch_license_validation(payload.username, payload.device_name or row["device_name"] or "dispositivo")
    fresh = fetch_license_by_username(payload.username)
    return _build_license_payload(fresh)


@app.get("/api/v1/admin/licenses")
def admin_list_licenses(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    _require_admin_token(x_admin_token)
    return [_row_to_admin_payload(row) for row in list_licenses()]


@app.post("/api/v1/admin/licenses")
def admin_create_license(
    payload: AdminCreateLicenseRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    _require_admin_token(x_admin_token)
    if fetch_license_by_username(payload.username):
        raise HTTPException(status_code=409, detail="Já existe uma licença com esse login.")

    expires_at = payload.expires_at.strip() if payload.expires_at else None
    if expires_at:
        parsed = parse_iso(expires_at)
        if not parsed:
            raise HTTPException(status_code=400, detail="Formato de validade inválido. Use ISO 8601.")
        expires_at = parsed.isoformat()

    create_license(
        payload.username,
        payload.password,
        expires_at=expires_at,
        notes=(payload.notes or "").strip(),
    )
    return {"ok": True}


@app.post("/api/v1/admin/licenses/{username}/revoke")
def admin_revoke_license(username: str, x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    _require_admin_token(x_admin_token)
    if not fetch_license_by_username(username):
        raise HTTPException(status_code=404, detail="Licença não encontrada.")
    update_status(username, "revoked")
    return {"ok": True}


@app.post("/api/v1/admin/licenses/{username}/reactivate")
def admin_reactivate_license(
    username: str,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    _require_admin_token(x_admin_token)
    if not fetch_license_by_username(username):
        raise HTTPException(status_code=404, detail="Licença não encontrada.")
    update_status(username, "active")
    return {"ok": True}


@app.post("/api/v1/admin/licenses/{username}/reset-device")
def admin_reset_device(username: str, x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    _require_admin_token(x_admin_token)
    if not fetch_license_by_username(username):
        raise HTTPException(status_code=404, detail="Licença não encontrada.")
    reset_device(username)
    return {"ok": True}


@app.post("/api/v1/admin/licenses/{username}/expiration")
def admin_change_expiration(
    username: str,
    payload: AdminExpirationRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    _require_admin_token(x_admin_token)
    if not fetch_license_by_username(username):
        raise HTTPException(status_code=404, detail="Licença não encontrada.")

    expires_at = payload.expires_at.strip() if payload.expires_at else None
    if expires_at:
        parsed = parse_iso(expires_at)
        if not parsed:
            raise HTTPException(status_code=400, detail="Formato de validade inválido. Use ISO 8601.")
        expires_at = parsed.isoformat()
    set_expiration(username, expires_at)
    return {"ok": True}


@app.delete("/api/v1/admin/licenses/{username}")
def admin_delete_license(username: str, x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")):
    _require_admin_token(x_admin_token)
    if not fetch_license_by_username(username):
        raise HTTPException(status_code=404, detail="Licença não encontrada.")
    delete_license(username)
    return {"ok": True}
