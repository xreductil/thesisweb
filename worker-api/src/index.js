const JSON_HEADERS = { "Content-Type": "application/json; charset=UTF-8" };

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...JSON_HEADERS, ...extraHeaders },
  });
}

function withCors(response) {
  const headers = new Headers(response.headers);
  headers.set("Access-Control-Allow-Origin", "*");
  headers.set("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Content-Type, Authorization");
  headers.set("Access-Control-Max-Age", "86400");
  return new Response(response.body, { status: response.status, headers });
}

function base64url(value) {
  const bytes = value instanceof ArrayBuffer ? new Uint8Array(value) : value;
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function decodeBase64url(value) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "===";
  const binary = atob(padded.slice(0, padded.length - (padded.length % 4)));
  return Uint8Array.from(binary, char => char.charCodeAt(0));
}

async function hmacKey(secret, usages) {
  return crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    usages,
  );
}

async function createToken(secret) {
  const header = base64url(new TextEncoder().encode(JSON.stringify({ alg: "HS256", typ: "JWT" })));
  const payload = base64url(new TextEncoder().encode(JSON.stringify({
    admin: true,
    exp: Math.floor(Date.now() / 1000) + 8 * 60 * 60,
  })));
  const unsigned = header + "." + payload;
  const signature = await crypto.subtle.sign(
    "HMAC",
    await hmacKey(secret, ["sign"]),
    new TextEncoder().encode(unsigned),
  );
  return unsigned + "." + base64url(signature);
}

async function verifyToken(token, secret) {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return false;
    const unsigned = parts[0] + "." + parts[1];
    const valid = await crypto.subtle.verify(
      "HMAC",
      await hmacKey(secret, ["verify"]),
      decodeBase64url(parts[2]),
      new TextEncoder().encode(unsigned),
    );
    if (!valid) return false;
    const claims = JSON.parse(new TextDecoder().decode(decodeBase64url(parts[1])));
    return claims.admin === true && claims.exp > Math.floor(Date.now() / 1000);
  } catch {
    return false;
  }
}

function getToken(request) {
  const authorization = request.headers.get("Authorization") || "";
  return authorization.startsWith("Bearer ") ? authorization.slice(7) : "";
}

async function requireAdmin(request, env) {
  if (!env.JWT_SECRET || !(await verifyToken(getToken(request), env.JWT_SECRET))) {
    return json({ error: "未授權" }, 401);
  }
  return null;
}

function formatDate(value, withTime = false) {
  const text = String(value || "").replace("T", " ");
  return withTime ? text.slice(0, 16) : text.slice(0, 10);
}

async function handle(request, env) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204 });

  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";

  if (path === "/health" && request.method === "GET") {
    return json({ ok: true, service: "thesis-api" });
  }

  if (path === "/api/admin/login" && request.method === "POST") {
    if (!env.ADMIN_PASSWORD || !env.JWT_SECRET) {
      return json({ error: "管理員密碼尚未設定" }, 503);
    }
    const data = await request.json().catch(() => ({}));
    if (data.password !== env.ADMIN_PASSWORD) return json({ error: "密碼錯誤" }, 401);
    return json({ success: true, token: await createToken(env.JWT_SECRET) });
  }

  if (path === "/api/admin/logout" && request.method === "POST") {
    return json({ success: true });
  }

  if (path === "/api/admin/check" && request.method === "GET") {
    const authorized = await requireAdmin(request, env);
    return authorized ? authorized : json({ logged_in: true });
  }

  if (path === "/api/reviews" && request.method === "GET") {
    const result = await env.DB.prepare(
      "SELECT id, content, rating, created_at FROM reviews WHERE visible = 1 ORDER BY created_at DESC",
    ).all();
    return json(result.results.map(row => ({ ...row, created_at: formatDate(row.created_at) })));
  }

  if (path === "/api/reviews" && request.method === "POST") {
    const data = await request.json().catch(() => ({}));
    const content = typeof data.content === "string" ? data.content.trim() : "";
    const rating = data.rating;
    if (!content) return json({ error: "請填寫評論內容" }, 400);
    if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
      return json({ error: "請選擇評分 (1-5)" }, 400);
    }
    const result = await env.DB.prepare(
      "INSERT INTO reviews (content, rating) VALUES (?, ?)",
    ).bind(content, rating).run();
    return json({ success: true, id: result.meta.last_row_id }, 201);
  }

  const adminError = await requireAdmin(request, env);
  if (adminError) return adminError;

  if (path === "/api/admin/reviews" && request.method === "GET") {
    const result = await env.DB.prepare(
      "SELECT id, content, rating, visible, created_at FROM reviews ORDER BY created_at DESC",
    ).all();
    return json(result.results.map(row => ({
      ...row,
      visible: Boolean(row.visible),
      created_at: formatDate(row.created_at, true),
    })));
  }

  const match = path.match(/^\/api\/admin\/reviews\/(\d+)(?:\/(toggle))?$/);
  if (match && request.method === "DELETE" && !match[2]) {
    await env.DB.prepare("DELETE FROM reviews WHERE id = ?").bind(Number(match[1])).run();
    return json({ success: true });
  }

  if (match && request.method === "PATCH" && match[2] === "toggle") {
    const id = Number(match[1]);
    const result = await env.DB.prepare(
      "UPDATE reviews SET visible = CASE visible WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
    ).bind(id).run();
    if (!result.meta.changes) return json({ error: "找不到評論" }, 404);
    const row = await env.DB.prepare("SELECT visible FROM reviews WHERE id = ?").bind(id).first();
    return json({ success: true, visible: Boolean(row.visible) });
  }

  return json({ error: "找不到 API 路徑" }, 404);
}

export default {
  async fetch(request, env) {
    try {
      return withCors(await handle(request, env));
    } catch (error) {
      console.error(error);
      return withCors(json({ error: "伺服器錯誤" }, 500));
    }
  },
};
