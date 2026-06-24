/**
 * 蓝宝书Max · 一人一码鉴权 Worker
 * 部署到 Cloudflare Workers + KV
 *
 * API:
 *   POST /bind     — 首次绑码（code + fingerprint → success/used）
 *   POST /verify   — 验证（code + fingerprint → valid/invalid）
 *   POST /unbind   — admin 解绑（admin_key + code → success）
 */

// ===== admin 密钥 =====
// 部署后改掉这个默认值
const ADMIN_KEY = "bbmax-admin-2026";

// ===== 设备指纹 =====
// 客户端传来的: browser + screen + timezone 的 SHA-256
// 加上 IP 地址做辅助验证

function getClientIP(request) {
  return request.headers.get("CF-Connecting-IP") || "unknown";
}

// ===== KV 操作 =====
async function getSub(code, env) {
  try {
    return JSON.parse(await env.SUBS.get(code) || "{}");
  } catch { return {}; }
}

async function setSub(code, data, env) {
  await env.SUBS.put(code, JSON.stringify(data));
}

// ===== 处理 =====
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    const ip = getClientIP(request);

    // CORS
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    }

    const corsHeaders = { "Access-Control-Allow-Origin": "*" };

    try {
      const body = await request.json();
      const { code, fingerprint, admin_key } = body;

      // ===== POST /bind — 首次绑码 =====
      if (path === "/bind" && request.method === "POST") {
        if (!code || !fingerprint) {
          return Response.json({ ok: false, reason: "missing_params" }, { headers: corsHeaders });
        }

        const sub = await getSub(code, env);

        // 已绑定 + 不同设备 → 拒绝
        if (sub.fingerprint && sub.fingerprint !== fingerprint) {
          return Response.json({
            ok: false,
            reason: "already_bound",
            boundAt: sub.boundAt,
            message: "此访问码已被其他设备绑定，请联系管理员。",
          }, { headers: corsHeaders });
        }

        // 已绑定 + 同设备 → 放行（换浏览器/清缓存场景）
        if (sub.fingerprint === fingerprint) {
          return Response.json({
            ok: true,
            reason: "already_own",
            boundAt: sub.boundAt,
            message: "已在此设备绑定，直接放行。",
          }, { headers: corsHeaders });
        }

        // 首次绑定
        const now = new Date().toISOString();
        await setSub(code, {
          fingerprint,
          ip,
          boundAt: now,
          lastAccess: now,
        }, env);

        return Response.json({
          ok: true,
          reason: "bound",
          boundAt: now,
          message: "绑定成功！欢迎加入蓝宝书Max。",
        }, { headers: corsHeaders });
      }

      // ===== POST /verify — 验证 =====
      if (path === "/verify" && request.method === "POST") {
        if (!code || !fingerprint) {
          return Response.json({ ok: false, reason: "missing_params" }, { headers: corsHeaders });
        }

        const sub = await getSub(code, env);

        if (!sub.fingerprint) {
          return Response.json({ ok: false, reason: "not_bound", message: "此码尚未被绑定。" }, { headers: corsHeaders });
        }

        if (sub.fingerprint !== fingerprint) {
          return Response.json({
            ok: false,
            reason: "device_mismatch",
            message: "此码已在其他设备使用。如已更换设备，请联系管理员。",
          }, { headers: corsHeaders });
        }

        // 更新最后访问时间
        sub.lastAccess = new Date().toISOString();
        await setSub(code, sub, env);

        return Response.json({
          ok: true,
          reason: "valid",
          boundAt: sub.boundAt,
          message: "验证通过。",
        }, { headers: corsHeaders });
      }

      // ===== POST /unbind — admin 解绑 =====
      if (path === "/unbind" && request.method === "POST") {
        if (admin_key !== ADMIN_KEY) {
          return Response.json({ ok: false, reason: "unauthorized" }, { headers: corsHeaders, status: 403 });
        }

        await env.SUBS.delete(code);
        return Response.json({ ok: true, reason: "unbound", message: "已解绑，此码可重新分配。" }, { headers: corsHeaders });
      }

      return Response.json({ ok: false, reason: "not_found" }, { headers: corsHeaders, status: 404 });

    } catch (e) {
      return Response.json({ ok: false, reason: "error", message: e.message }, { headers: corsHeaders, status: 500 });
    }
  },
};
