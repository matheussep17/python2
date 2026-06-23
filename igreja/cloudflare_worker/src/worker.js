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
  if (path === `${PREFIX}/favicon.svg` && (method === "GET" || method === "HEAD")) {
    return svg(churchFavicon());
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
  const grace = positiveInt(env.OFFLINE_GRACE_HOURS, 24);
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

function svg(content) {
  return new Response(content, {
    headers: {
      "content-type": "image/svg+xml; charset=utf-8",
      "cache-control": "public, max-age=86400",
    },
  });
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
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#07111f"><link rel="icon" href="${PREFIX}/favicon.svg" type="image/svg+xml"><title>Licenças | App Igreja</title>
<style>
*{box-sizing:border-box}
:root{color-scheme:dark;--bg:#07111f;--panel:#0e1d30;--panel2:#13263d;--line:#263d57;--text:#f4f8fc;--muted:#9eb0c3;--cyan:#46d7e8;--green:#78e6b1;--red:#ff7d86;--yellow:#f4c96b}
body{min-height:100vh;margin:0;color:var(--text);background:radial-gradient(circle at 85% 0,rgba(79,124,255,.2),transparent 34rem),var(--bg);font:15px/1.5 Inter,system-ui,-apple-system,"Segoe UI",sans-serif}
main{width:min(1180px,calc(100% - 32px));margin:auto;padding:42px 0 70px}
.topbar{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:25px}
.eyebrow{margin:0 0 5px;color:var(--cyan);font:700 12px monospace;letter-spacing:.12em;text-transform:uppercase}
h1{margin:0;font-size:clamp(2rem,5vw,3.5rem);letter-spacing:-.055em;line-height:1}h2{margin:0 0 18px;font-size:1.25rem}
.health{display:inline-flex;align-items:center;gap:8px;color:var(--green);font-size:13px}.health:before{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 14px var(--green);content:""}
.card{margin:14px 0;border:1px solid var(--line);border-radius:18px;padding:22px;background:rgba(14,29,48,.9);box-shadow:0 18px 50px rgba(0,0,0,.16)}
.auth-row{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:end}.field-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
label{display:grid;gap:7px;color:var(--muted);font-size:13px;font-weight:650}
input{width:100%;min-height:46px;border:1px solid var(--line);border-radius:11px;padding:0 13px;color:var(--text);background:#081522;font:inherit;outline:none}
input:focus{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(70,215,232,.12)}
button{min-height:42px;border:1px solid var(--line);border-radius:10px;padding:0 15px;color:var(--text);background:#182c44;font:700 13px system-ui;cursor:pointer;transition:transform .15s,border-color .15s,filter .15s}
button:hover{transform:translateY(-1px);border-color:#4b6b8c;filter:brightness(1.08)}
.primary{border-color:transparent;color:#06121d;background:linear-gradient(120deg,var(--cyan),var(--green))}
.warning{border-color:rgba(244,201,107,.3);color:var(--yellow);background:rgba(244,201,107,.1)}
.destructive{border-color:rgba(255,125,134,.3);color:#ffadb3;background:rgba(255,125,134,.1)}
#status{display:block;min-height:22px;margin-top:12px;color:var(--green);font-size:13px;white-space:pre-wrap}.danger{color:var(--red)!important}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:13px}
table{width:100%;border-collapse:collapse;min-width:850px;background:#0a1827}th,td{padding:14px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
th{color:var(--muted);background:#102238;font-size:11px;letter-spacing:.08em;text-transform:uppercase}tbody tr:last-child td{border-bottom:0}tbody tr:hover{background:rgba(70,215,232,.035)}
.user{font-weight:750}.device{color:var(--muted)}.badge{display:inline-flex;border:1px solid rgba(120,230,177,.3);border-radius:999px;padding:4px 9px;color:var(--green);background:rgba(120,230,177,.08);font-size:11px;font-weight:800;text-transform:uppercase}
.badge.revoked{border-color:rgba(255,125,134,.3);color:var(--red);background:rgba(255,125,134,.08)}
.actions{display:flex;flex-wrap:wrap;gap:7px}.actions button{min-height:34px;padding:0 10px;font-size:12px}
.empty{text-align:center!important;color:var(--muted);padding:32px!important}
.hidden{display:none!important}
@media(max-width:700px){main{width:min(100% - 20px,1180px);padding-top:25px}.topbar{align-items:start;flex-direction:column}.auth-row,.field-grid{grid-template-columns:1fr}.auth-row button{width:100%}.card{padding:16px}}
</style></head><body><main>
<div class="topbar"><div><p class="eyebrow">App Igreja</p><h1>Painel de licenças</h1></div><span class="health">Servidor operacional</span></div>
<section class="card" id="auth-card"><form id="auth-form" class="auth-row"><label>Token administrativo<input id="token" type="password" autocomplete="current-password" placeholder="Digite o token para acessar"></label>
<button class="primary" type="submit">Acessar painel</button></form><span id="auth-status">Informe o token para carregar as licenças.</span></section>
<div id="admin-panel" class="hidden">
<section class="card"><h2>Nova licença</h2><form id="license-form"><div class="field-grid">
<label>Login<input id="username" placeholder="Nome da licença"></label>
<label>Senha<input id="password" type="password" placeholder="Mínimo de 8 caracteres"></label>
<label>Validade<input id="expires" placeholder="ISO 8601 (opcional)"></label>
<label>Observações<input id="notes" placeholder="Informações administrativas"></label>
</div><button class="primary" type="submit" style="margin-top:16px">Criar licença</button></form></section>
<section class="card"><h2>Licenças cadastradas</h2><div class="table-wrap"><table><thead><tr><th>Login</th><th>Status</th><th>Dispositivo</th><th>Validade</th><th>Ações</th></tr></thead>
<tbody id="rows"><tr><td colspan="5" class="empty">A lista será exibida após informar o token.</td></tr></tbody></table></div></section>
<span id="panel-status"></span>
</div>
</main><script>
const api="${API_PREFIX}";
let adminToken="";
let authenticated=false;
const token=()=>adminToken||document.querySelector("#token").value;
function status(text,bad=false){const el=document.querySelector(authenticated?"#panel-status":"#auth-status");el.textContent=" "+text;el.className=bad?"danger":""}
async function call(path,options={}){options.headers={...(options.headers||{}),"Content-Type":"application/json","X-Admin-Token":token()};
 const response=await fetch(api+path,options);const data=await response.json();if(!response.ok)throw new Error(data.detail||"Falha");return data}
async function load(){try{adminToken=document.querySelector("#token").value;const data=await call("/admin/licenses");authenticated=true;document.querySelector("#auth-card").classList.add("hidden");document.querySelector("#admin-panel").classList.remove("hidden");document.querySelector("#rows").innerHTML=data.map(row=>\`
<tr><td class="user">\${row.username}</td><td><span class="badge \${row.status==="active"?"":"revoked"}">\${row.status==="active"?"Ativa":"Revogada"}</span></td><td class="device">\${row.device_name||"Não vinculado"}</td><td>\${row.expires_at||"Permanente"}</td>
<td><div class="actions"><button class="\${row.status==="active"?"warning":""}" onclick="action('\${encodeURIComponent(row.username)}','\${row.status==="active"?"revoke":"reactivate"}')">\${row.status==="active"?"Revogar":"Reativar"}</button>
<button onclick="action('\${encodeURIComponent(row.username)}','reset-device')">Liberar PC</button>
<button class="destructive" onclick="removeLicense('\${encodeURIComponent(row.username)}')">Excluir</button></div></td></tr>\`).join("")||'<tr><td colspan="5" class="empty">Nenhuma licença cadastrada.</td></tr>';status(data.length+" licença(s) carregada(s).")}catch(e){status(e.message,true)}}
async function createLicense(){try{await call("/admin/licenses",{method:"POST",body:JSON.stringify({username:username.value,password:password.value,expires_at:expires.value||null,notes:notes.value})});document.querySelector("#license-form").reset();await load()}catch(e){status(e.message,true)}}
async function action(user,name){try{await call("/admin/licenses/"+user+"/"+name,{method:"POST",body:"{}"});await load()}catch(e){status(e.message,true)}}
async function removeLicense(user){if(!confirm("Excluir esta licença definitivamente?"))return;try{await call("/admin/licenses/"+user,{method:"DELETE"});await load()}catch(e){status(e.message,true)}}
document.querySelector("#auth-form").addEventListener("submit",event=>{event.preventDefault();load()});
document.querySelector("#license-form").addEventListener("submit",event=>{event.preventDefault();createLicense()});
</script></body></html>`;
}

function churchFavicon() {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs><linearGradient id="bg" x1="8" y1="6" x2="56" y2="58" gradientUnits="userSpaceOnUse"><stop stop-color="#4f7cff"/><stop offset="1" stop-color="#46d7e8"/></linearGradient></defs>
  <rect width="64" height="64" rx="16" fill="#07111f"/>
  <path d="M27 10h10v14h13v10H37v20H27V34H14V24h13V10Z" fill="url(#bg)"/>
  <path d="M32 13v37M17 29h30" stroke="#f4f8fc" stroke-width="3" stroke-linecap="round" opacity=".85"/>
</svg>`;
}
