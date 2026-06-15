import { scrypt } from "scrypt-js";

const PREFIX = "/appigreja";
const API_PREFIX = `${PREFIX}/api/v1`;
const encoder = new TextEncoder();

export default {
  async fetch(request, env) {
    try {
      return await route(request, env);
    } catch (error) {
      console.error(error);
      if (error && Number.isInteger(error.status)) {
        return json({ detail: error.message }, error.status);
      }
      return json({ detail: "Erro interno do servidor." }, 500);
    }
  },
};

async function route(request, env) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const method = request.method.toUpperCase();

  if (method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders() });
  }
  if (path === PREFIX && method === "GET") {
    return Response.redirect(`${url.origin}${PREFIX}/admin`, 302);
  }
  if (path === `${PREFIX}/health` && method === "GET") {
    return json({ status: "ok" });
  }
  if (path === `${PREFIX}/privacy` && method === "GET") {
    return privacyNotice(env);
  }
  if (path === `${PREFIX}/admin` && method === "GET") {
    return html(adminPage());
  }
  if (path === `${API_PREFIX}/activate` && method === "POST") {
    return activate(request, env);
  }
  if (path === `${API_PREFIX}/validate` && method === "POST") {
    return validate(request, env);
  }
  if (path === `${API_PREFIX}/admin/licenses` && method === "GET") {
    requireAdmin(request, env);
    return listLicenses(env);
  }
  if (path === `${API_PREFIX}/admin/licenses` && method === "POST") {
    requireAdmin(request, env);
    return createLicense(request, env);
  }
  if (path === `${API_PREFIX}/admin/backup` && method === "GET") {
    requireAdmin(request, env);
    return backupLicenses(env);
  }
  if (path === `${API_PREFIX}/admin/import` && method === "POST") {
    requireAdmin(request, env);
    return importLicenses(request, env);
  }
  if (path === `${API_PREFIX}/admin/privacy/purge` && method === "POST") {
    requireAdmin(request, env);
    return purgeInactive(env);
  }

  const licenseAction = path.match(
    new RegExp(`^${API_PREFIX}/admin/licenses/([^/]+)/(revoke|reactivate|reset-device|expiration)$`),
  );
  if (licenseAction && method === "POST") {
    requireAdmin(request, env);
    return mutateLicense(decodeURIComponent(licenseAction[1]), licenseAction[2], request, env);
  }

  const licenseDelete = path.match(new RegExp(`^${API_PREFIX}/admin/licenses/([^/]+)$`));
  if (licenseDelete && method === "DELETE") {
    requireAdmin(request, env);
    return deleteLicense(decodeURIComponent(licenseDelete[1]), env);
  }

  const privacyExport = path.match(new RegExp(`^${API_PREFIX}/admin/privacy/export/([^/]+)$`));
  if (privacyExport && method === "GET") {
    requireAdmin(request, env);
    return exportPrivacy(decodeURIComponent(privacyExport[1]), env);
  }

  const privacyAnonymize = path.match(new RegExp(`^${API_PREFIX}/admin/privacy/anonymize/([^/]+)$`));
  if (privacyAnonymize && method === "POST") {
    requireAdmin(request, env);
    return anonymizeLicense(decodeURIComponent(privacyAnonymize[1]), request, env);
  }

  return json({ detail: "Rota nao encontrada." }, 404);
}

async function activate(request, env) {
  const payload = await readJson(request);
  requireText(payload.username, "username", 1, 120);
  requireText(payload.password, "password", 1, 200);
  requireText(payload.device_fingerprint, "device_fingerprint", 16, 128);

  const row = await findLicense(env, payload.username);
  ensureUsable(row);
  if (!(await verifyPassword(payload.password, row.password_hash))) {
    throw httpError(401, "Login ou senha invalidos.");
  }

  const fingerprints = knownFingerprints(payload);
  if (row.device_fingerprint && !fingerprints.has(row.device_fingerprint)) {
    throw httpError(409, "Esta licenca ja esta vinculada a outro computador.");
  }

  const now = new Date().toISOString();
  const token = row.activation_token || randomToken(32);
  await env.DB.prepare(
    `UPDATE licenses
     SET device_fingerprint = ?, device_name = ?, activation_token = ?,
         activated_at = COALESCE(activated_at, ?), last_validated_at = ?
     WHERE username = ?`,
  ).bind(
    payload.device_fingerprint,
    cleanText(payload.device_name, "dispositivo"),
    token,
    now,
    now,
    payload.username.trim(),
  ).run();

  return json(licensePayload(await findLicense(env, payload.username), env));
}

async function validate(request, env) {
  const payload = await readJson(request);
  requireText(payload.username, "username", 1, 120);
  requireText(payload.activation_token, "activation_token", 1, 200);
  requireText(payload.device_fingerprint, "device_fingerprint", 16, 128);

  const row = await findLicense(env, payload.username);
  ensureUsable(row);
  if (row.activation_token !== payload.activation_token) {
    throw httpError(401, "Token de ativacao invalido para este login.");
  }
  if (!knownFingerprints(payload).has(row.device_fingerprint)) {
    throw httpError(409, "Esta licenca pertence a outro computador.");
  }

  const now = new Date().toISOString();
  await env.DB.prepare(
    `UPDATE licenses
     SET device_fingerprint = ?, device_name = ?, last_validated_at = ?
     WHERE username = ?`,
  ).bind(
    payload.device_fingerprint,
    cleanText(payload.device_name, row.device_name || "dispositivo"),
    now,
    payload.username.trim(),
  ).run();

  return json(licensePayload(await findLicense(env, payload.username), env));
}

async function listLicenses(env) {
  const result = await env.DB.prepare(
    `SELECT id, username, status, device_name, device_fingerprint,
            created_at, activated_at, last_validated_at, expires_at, notes
     FROM licenses WHERE privacy_deleted_at IS NULL ORDER BY username`,
  ).all();
  return json(result.results || []);
}

async function createLicense(request, env) {
  const payload = await readJson(request);
  requireText(payload.username, "username", 1, 120);
  requireText(payload.password, "password", 8, 200);
  const existing = await env.DB.prepare("SELECT id FROM licenses WHERE username = ?")
    .bind(payload.username.trim()).first();
  if (existing) {
    throw httpError(409, "Ja existe uma licenca com esse login.");
  }
  const expiresAt = normalizeDate(payload.expires_at);
  await env.DB.prepare(
    `INSERT INTO licenses (username, password_hash, status, created_at, expires_at, notes)
     VALUES (?, ?, 'active', ?, ?, ?)`,
  ).bind(
    payload.username.trim(),
    await hashPassword(payload.password),
    new Date().toISOString(),
    expiresAt,
    cleanText(payload.notes),
  ).run();
  return json({ ok: true });
}

async function mutateLicense(username, action, request, env) {
  const row = await findLicense(env, username);
  if (!row) throw httpError(404, "Licenca nao encontrada.");

  if (action === "revoke" || action === "reactivate") {
    await env.DB.prepare("UPDATE licenses SET status = ? WHERE username = ?")
      .bind(action === "revoke" ? "revoked" : "active", username.trim()).run();
  } else if (action === "reset-device") {
    await env.DB.prepare(
      `UPDATE licenses SET device_fingerprint = NULL, device_name = NULL,
       activation_token = NULL, activated_at = NULL WHERE username = ?`,
    ).bind(username.trim()).run();
  } else {
    const payload = await readJson(request);
    await env.DB.prepare("UPDATE licenses SET expires_at = ? WHERE username = ?")
      .bind(normalizeDate(payload.expires_at), username.trim()).run();
  }
  return json({ ok: true });
}

async function deleteLicense(username, env) {
  if (!(await findLicense(env, username))) throw httpError(404, "Licenca nao encontrada.");
  await env.DB.prepare("DELETE FROM licenses WHERE username = ?").bind(username.trim()).run();
  return json({ ok: true });
}

async function exportPrivacy(username, env) {
  const row = await env.DB.prepare(
    `SELECT id AS license_id, username, status, device_name, device_fingerprint,
            created_at, activated_at, last_validated_at, expires_at, notes,
            privacy_deleted_at, privacy_erasure_reason
     FROM licenses WHERE username = ?`,
  ).bind(username.trim()).first();
  if (!row) throw httpError(404, "Licenca nao encontrada.");
  return json(row);
}

async function anonymizeLicense(username, request, env) {
  const row = await findLicense(env, username);
  if (!row) throw httpError(404, "Licenca nao encontrada.");
  const payload = await readJson(request);
  await env.DB.prepare(
    `UPDATE licenses SET username = ?, password_hash = ?, status = 'revoked',
     device_fingerprint = NULL, device_name = NULL, activation_token = NULL,
     notes = NULL, privacy_deleted_at = ?, privacy_erasure_reason = ?
     WHERE username = ?`,
  ).bind(
    `apagado-${row.id}-${randomToken(4)}`,
    await hashPassword(randomToken(32)),
    new Date().toISOString(),
    cleanText(payload.reason),
    username.trim(),
  ).run();
  return json({ ok: true });
}

async function purgeInactive(env) {
  const days = positiveInt(env.PRIVACY_RETENTION_DAYS, 1095);
  const cutoff = new Date(Date.now() - days * 86400000).toISOString();
  const result = await env.DB.prepare(
    `UPDATE licenses SET device_fingerprint = NULL, device_name = NULL,
     activation_token = NULL, notes = NULL,
     privacy_deleted_at = COALESCE(privacy_deleted_at, ?),
     privacy_erasure_reason = COALESCE(privacy_erasure_reason, 'retention_period_expired')
     WHERE privacy_deleted_at IS NULL AND status != 'active'
     AND COALESCE(last_validated_at, activated_at, created_at) < ?`,
  ).bind(new Date().toISOString(), cutoff).run();
  return json({ ok: true, purged: result.meta?.changes || 0 });
}

async function backupLicenses(env) {
  const result = await env.DB.prepare("SELECT * FROM licenses ORDER BY id").all();
  return json({ version: 1, licenses: result.results || [] });
}

async function importLicenses(request, env) {
  const payload = await readJson(request);
  if (!Array.isArray(payload.licenses)) throw httpError(400, "Informe a lista 'licenses'.");
  let imported = 0;
  for (const row of payload.licenses) {
    requireText(row.username, "username", 1, 120);
    requireText(row.password_hash, "password_hash", 10, 500);
    await env.DB.prepare(
      `INSERT INTO licenses (
        id, username, password_hash, status, device_fingerprint, device_name,
        activation_token, created_at, activated_at, last_validated_at,
        expires_at, notes, privacy_deleted_at, privacy_erasure_reason
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(username) DO UPDATE SET
        password_hash=excluded.password_hash, status=excluded.status,
        device_fingerprint=excluded.device_fingerprint, device_name=excluded.device_name,
        activation_token=excluded.activation_token, created_at=excluded.created_at,
        activated_at=excluded.activated_at, last_validated_at=excluded.last_validated_at,
        expires_at=excluded.expires_at, notes=excluded.notes,
        privacy_deleted_at=excluded.privacy_deleted_at,
        privacy_erasure_reason=excluded.privacy_erasure_reason`,
    ).bind(
      row.id || null, row.username, row.password_hash, row.status || "active",
      row.device_fingerprint || null, row.device_name || null, row.activation_token || null,
      row.created_at || new Date().toISOString(), row.activated_at || null,
      row.last_validated_at || null, row.expires_at || null, row.notes || null,
      row.privacy_deleted_at || null, row.privacy_erasure_reason || null,
    ).run();
    imported += 1;
  }
  return json({ ok: true, imported });
}

async function findLicense(env, username) {
  return env.DB.prepare(
    "SELECT * FROM licenses WHERE username = ? AND privacy_deleted_at IS NULL",
  ).bind(String(username || "").trim()).first();
}

function ensureUsable(row) {
  if (!row) throw httpError(401, "Login ou senha invalidos.");
  if (row.status !== "active") throw httpError(403, "Esta licenca esta bloqueada.");
  if (row.expires_at && Date.now() > Date.parse(row.expires_at)) {
    throw httpError(403, "Esta licenca expirou e precisa ser renovada.");
  }
}

function licensePayload(row, env) {
  const now = new Date();
  const grace = positiveInt(env.OFFLINE_GRACE_HOURS, 175200);
  return {
    license_id: row.id,
    username: row.username,
    status: row.status,
    device_fingerprint: row.device_fingerprint,
    device_name: row.device_name,
    activation_token: row.activation_token,
    expires_at: row.expires_at,
    validated_at: now.toISOString(),
    offline_valid_until: new Date(now.getTime() + grace * 3600000).toISOString(),
  };
}

async function hashPassword(password, salt = null) {
  const rawSalt = salt || crypto.getRandomValues(new Uint8Array(16));
  const digest = await scrypt(encoder.encode(password), rawSalt, 16384, 8, 1, 64);
  return `${toHex(rawSalt)}$${toHex(digest)}`;
}

async function verifyPassword(password, encoded) {
  try {
    const [saltHex, expectedHex] = String(encoded).split("$", 2);
    const actual = await hashPassword(password, fromHex(saltHex));
    return timingSafeEqual(actual.split("$", 2)[1], expectedHex);
  } catch {
    return false;
  }
}

function knownFingerprints(payload) {
  const values = [payload.device_fingerprint, ...(payload.legacy_device_fingerprints || [])];
  return new Set(values.map((item) => String(item || "").trim().slice(0, 128))
    .filter((item) => item.length >= 16));
}

function requireAdmin(request, env) {
  if (!env.ADMIN_TOKEN) throw httpError(503, "Configure o segredo ADMIN_TOKEN.");
  if (request.headers.get("X-Admin-Token") !== env.ADMIN_TOKEN) {
    throw httpError(401, "Token administrativo invalido.");
  }
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    throw httpError(400, "JSON invalido.");
  }
}

function requireText(value, field, min, max) {
  const size = String(value || "").length;
  if (size < min || size > max) throw httpError(422, `Campo '${field}' invalido.`);
}

function normalizeDate(value) {
  const text = cleanText(value);
  if (!text) return null;
  const timestamp = Date.parse(text);
  if (Number.isNaN(timestamp)) throw httpError(400, "Formato de validade invalido. Use ISO 8601.");
  return new Date(timestamp).toISOString();
}

function cleanText(value, fallback = "") {
  const text = String(value || "").trim();
  return text || fallback;
}

function positiveInt(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function randomToken(bytes) {
  const data = crypto.getRandomValues(new Uint8Array(bytes));
  return btoa(String.fromCharCode(...data)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function toHex(data) {
  return [...data].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function fromHex(value) {
  if (!value || value.length % 2) throw new Error("hex invalido");
  return new Uint8Array(value.match(/.{2}/g).map((part) => Number.parseInt(part, 16)));
}

function timingSafeEqual(left, right) {
  if (left.length !== right.length) return false;
  let mismatch = 0;
  for (let index = 0; index < left.length; index += 1) {
    mismatch |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return mismatch === 0;
}

function httpError(status, detail) {
  const error = new Error(detail);
  error.status = status;
  return error;
}

function json(payload, status = 200) {
  const effectiveStatus = payload instanceof Error ? payload.status || 500 : status;
  const body = payload instanceof Error ? { detail: payload.message } : payload;
  return new Response(JSON.stringify(body), {
    status: effectiveStatus,
    headers: { "content-type": "application/json; charset=utf-8", ...corsHeaders() },
  });
}

function html(content) {
  return new Response(content, { headers: { "content-type": "text/html; charset=utf-8" } });
}

function corsHeaders() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "Content-Type, X-Admin-Token",
    "access-control-allow-methods": "GET, POST, DELETE, OPTIONS",
  };
}

function privacyNotice(env) {
  return json({
    service: "Igreja Licensing API",
    purpose: "Controle de ativacao, validacao e suporte de licencas do aplicativo.",
    retention_days_for_inactive_licenses: positiveInt(env.PRIVACY_RETENTION_DAYS, 1095),
    privacy_contact: env.PRIVACY_CONTACT || "Contato de privacidade nao configurado.",
  });
}

function adminPage() {
  return `<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Licencas Igreja</title>
<style>
body{font:16px system-ui;background:#0b1320;color:#eef4ff;margin:0}main{max-width:1050px;margin:auto;padding:28px}
input,button{font:inherit;padding:9px;margin:4px;border-radius:7px;border:1px solid #40506a}
button{cursor:pointer}.card{background:#111c2d;padding:18px;border-radius:12px;margin:14px 0}
table{width:100%;border-collapse:collapse}th,td{padding:9px;border-bottom:1px solid #2b3b56;text-align:left}
.actions button{padding:5px}#status{color:#67d5b5;white-space:pre-wrap}.danger{color:#ff8d85}
</style></head><body><main>
<h1>Painel de licencas</h1>
<div class="card"><label>Token administrativo <input id="token" type="password"></label>
<button onclick="load()">Atualizar</button><span id="status"></span></div>
<div class="card"><h2>Nova licenca</h2>
<input id="username" placeholder="Login"><input id="password" type="password" placeholder="Senha (8+ caracteres)">
<input id="expires" placeholder="Validade ISO (opcional)"><input id="notes" placeholder="Observacoes">
<button onclick="createLicense()">Criar</button></div>
<div class="card"><table><thead><tr><th>Login</th><th>Status</th><th>Dispositivo</th><th>Validade</th><th>Acoes</th></tr></thead>
<tbody id="rows"></tbody></table></div>
</main><script>
const api="${API_PREFIX}";
const token=()=>document.querySelector("#token").value;
function status(text,bad=false){const el=document.querySelector("#status");el.textContent=" "+text;el.className=bad?"danger":""}
async function call(path,options={}){options.headers={...(options.headers||{}),"Content-Type":"application/json","X-Admin-Token":token()};
 const response=await fetch(api+path,options);const data=await response.json();if(!response.ok)throw new Error(data.detail||"Falha");return data}
async function load(){try{const data=await call("/admin/licenses");document.querySelector("#rows").innerHTML=data.map(row=>\`
<tr><td>\${row.username}</td><td>\${row.status}</td><td>\${row.device_name||"-"}</td><td>\${row.expires_at||"Permanente"}</td>
<td class="actions"><button onclick="action('\${encodeURIComponent(row.username)}','\${row.status==="active"?"revoke":"reactivate"}')">\${row.status==="active"?"Revogar":"Reativar"}</button>
<button onclick="action('\${encodeURIComponent(row.username)}','reset-device')">Liberar PC</button>
<button onclick="removeLicense('\${encodeURIComponent(row.username)}')">Excluir</button></td></tr>\`).join("");status("Lista atualizada.")}catch(e){status(e.message,true)}}
async function createLicense(){try{await call("/admin/licenses",{method:"POST",body:JSON.stringify({username:username.value,password:password.value,expires_at:expires.value||null,notes:notes.value})});await load()}catch(e){status(e.message,true)}}
async function action(user,name){try{await call("/admin/licenses/"+user+"/"+name,{method:"POST",body:"{}"});await load()}catch(e){status(e.message,true)}}
async function removeLicense(user){if(!confirm("Excluir definitivamente?"))return;try{await call("/admin/licenses/"+user,{method:"DELETE"});await load()}catch(e){status(e.message,true)}}
</script></body></html>`;
}
