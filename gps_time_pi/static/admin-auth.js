// Admin requests for the legacy pages (/admin, /configure): POST + JSON + the
// station admin token (Authorization: Bearer). The token is kept in
// sessionStorage for this tab only. See docs/api/README.md, "Authentication".
const GTP_TOKEN_KEY = "gtp-admin-token";

function gtpToken() {
  try { return sessionStorage.getItem(GTP_TOKEN_KEY); } catch (e) { return null; }
}
function gtpSetToken(t) {
  try { if (t) sessionStorage.setItem(GTP_TOKEN_KEY, t); else sessionStorage.removeItem(GTP_TOKEN_KEY); } catch (e) {}
}
function gtpAskToken(reason) {
  const t = window.prompt((reason ? reason + "\n\n" : "") +
    "Admin token for this station (from: sudo python3 -m gps_time_pi.admin_token):");
  if (t) gtpSetToken(t.trim());
  return t ? t.trim() : null;
}

// POST JSON; asks for the token when the station requires one. Resolves to
// {status, body}; never throws for HTTP errors.
async function gtpAdminPost(path, payload) {
  let auth = null;
  try { auth = await (await fetch("/api/auth", { cache: "no-store" })).json(); } catch (e) {}
  if (auth && auth.auth_required && !auth.admin_configured) {
    return { status: 403, body: { ok: false, error: "admin is disabled on this station: create a token with sudo python3 -m gps_time_pi.admin_token" } };
  }
  let token = gtpToken();
  if (auth && auth.auth_required && !token) token = gtpAskToken();
  for (let attempt = 0; attempt < 2; attempt++) {
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;
    const r = await fetch(path, { method: "POST", headers, body: JSON.stringify(payload || {}), cache: "no-store" });
    let body = null;
    try { body = await r.json(); } catch (e) { body = { ok: false, error: "HTTP " + r.status }; }
    if (r.status === 401 && attempt === 0) {
      gtpSetToken(null);
      token = gtpAskToken("The token was not accepted.");
      if (!token) return { status: 401, body };
      continue;
    }
    return { status: r.status, body };
  }
}
