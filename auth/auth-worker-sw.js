/**
 * 蓝宝书Max · 设备绑定鉴权 Worker v1 (Service Worker 格式)
 * ======================================================
 *
 * 端点:
 *   POST /activate  — 验码 + Canvas指纹 + 签发 token + 绑定设备(≤2台)
 *   POST /verify    — 验 token（自包含，纯计算，不读KV）
 *   POST /unbind    — Admin 解绑设备
 *
 * Token 结构:
 *   base64(sha256(fp|secret|expires)).fp.expires
 *   验证只需一次 hash，~1ms，不读 KV
 *
 * KV 结构 (全局绑定):
 *   code:{CODE}  → { devices: [], expiresAt, createdAt }
 *   recover:{FP} → { code, lastIP, lastSeen }
 */

const TOKEN_EXPIRES_MS = 30 * 24 * 60 * 60 * 1000; // 30 天
const MAX_DEVICES = 2;
const RECOVER_DAYS = 30;

// ── 入口 ──
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  const url = new URL(request.url);
  const path = url.pathname;

  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
  };

  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  if (request.method !== 'POST') {
    return jsonResponse({ error: 'Method not allowed' }, 405, corsHeaders);
  }

  try {
    const body = await request.json();

    switch (path) {
      case '/activate':
        return handleActivate(body, corsHeaders, request);
      case '/verify':
        return handleVerify(body, corsHeaders);
      case '/unbind':
        return handleUnbind(body, corsHeaders);
      default:
        return jsonResponse({ error: 'Not found' }, 404, corsHeaders);
    }
  } catch (err) {
    return jsonResponse({ error: 'Internal error' }, 500, corsHeaders);
  }
}

// ════════════════════════════════════════════════════════════
//  POST /activate
// ════════════════════════════════════════════════════════════
async function handleActivate(body, corsHeaders, request) {
  const { code, fp } = body;
  if (!code || !fp) {
    return jsonResponse({ ok: false, error: '缺少激活码或设备指纹' }, 400, corsHeaders);
  }

  const codeKey = 'code:' + code;
  let codeData = await AUTH_CODES.get(codeKey, 'json');

  if (!codeData) {
    return jsonResponse({ ok: false, error: '无效的激活码' }, 403, corsHeaders);
  }

  if (Date.now() > new Date(codeData.expiresAt).getTime()) {
    return jsonResponse({ ok: false, error: '激活码已过期' }, 403, corsHeaders);
  }

  const devices = codeData.devices || [];

  // ── 情况1: 首次激活 ──
  if (devices.length === 0) {
    const token = await signToken(fp, TOKEN_SECRET);
    const deviceInfo = {
      fp,
      activatedAt: new Date().toISOString(),
      lastSeen: new Date().toISOString(),
    };
    devices.push(deviceInfo);
    await AUTH_CODES.put(codeKey, JSON.stringify({ ...codeData, devices, used: true }));
    await AUTH_CODES.put('recover:' + fp, JSON.stringify({
      code,
      lastIP: request.headers.get('CF-Connecting-IP') || '',
      lastSeen: new Date().toISOString(),
    }));
    return jsonResponse({
      ok: true,
      token,
      expires: Date.now() + TOKEN_EXPIRES_MS,
      devicesLeft: MAX_DEVICES - devices.length,
    }, 200, corsHeaders);
  }

  // ── 情况2: 已在设备列表中（清缓存恢复） ──
  const existingDevice = devices.find(d => d.fp === fp);
  if (existingDevice) {
    const token = await signToken(fp, TOKEN_SECRET);
    existingDevice.lastSeen = new Date().toISOString();
    await AUTH_CODES.put(codeKey, JSON.stringify({ ...codeData, devices }));
    return jsonResponse({
      ok: true,
      token,
      expires: Date.now() + TOKEN_EXPIRES_MS,
      devicesLeft: MAX_DEVICES - devices.length,
      recovered: true,
    }, 200, corsHeaders);
  }

  // ── 情况3: 设备已满 ──
  if (devices.length >= MAX_DEVICES) {
    const clientIP = request.headers.get('CF-Connecting-IP') || '';
    const lastDevice = devices[devices.length - 1];
    const daysSinceLast = (Date.now() - new Date(lastDevice.lastSeen).getTime())
      / (24 * 60 * 60 * 1000);

    if (daysSinceLast < RECOVER_DAYS) {
      return jsonResponse({
        ok: false,
        error: '已达设备上限(' + MAX_DEVICES + '台)，请联系管理员解绑',
        devicesLeft: 0,
      }, 403, corsHeaders);
    }

    // 超过30天无活跃 → 替换最早的设备
    const oldest = devices.reduce((a, b) =>
      new Date(a.lastSeen) < new Date(b.lastSeen) ? a : b
    );
    oldest.fp = fp;
    oldest.activatedAt = new Date().toISOString();
    oldest.lastSeen = new Date().toISOString();

    const token = await signToken(fp, TOKEN_SECRET);
    await AUTH_CODES.put(codeKey, JSON.stringify({ ...codeData, devices }));
    return jsonResponse({
      ok: true,
      token,
      expires: Date.now() + TOKEN_EXPIRES_MS,
      devicesLeft: 0,
      recovered: true,
    }, 200, corsHeaders);
  }

  // ── 情况4: 还有设备名额 → 绑新设备 ──
  const token = await signToken(fp, TOKEN_SECRET);
  const newDevice = {
    fp,
    activatedAt: new Date().toISOString(),
    lastSeen: new Date().toISOString(),
  };
  devices.push(newDevice);
  await AUTH_CODES.put(codeKey, JSON.stringify({ ...codeData, devices }));
  await AUTH_CODES.put('recover:' + fp, JSON.stringify({
    code,
    lastIP: request.headers.get('CF-Connecting-IP') || '',
    lastSeen: new Date().toISOString(),
  }));
  return jsonResponse({
    ok: true,
    token,
    expires: Date.now() + TOKEN_EXPIRES_MS,
    devicesLeft: MAX_DEVICES - devices.length,
  }, 200, corsHeaders);
}

// ════════════════════════════════════════════════════════════
//  POST /verify
// ════════════════════════════════════════════════════════════
async function handleVerify(body, corsHeaders) {
  const { token } = body;
  if (!token) {
    return jsonResponse({ ok: false, error: '缺少 token' }, 400, corsHeaders);
  }

  const result = await verifyToken(token, TOKEN_SECRET);
  if (!result.ok) {
    return jsonResponse({ ok: false, error: 'token 无效或已过期' }, 403, corsHeaders);
  }

  return jsonResponse({
    ok: true,
    fp: result.fp,
    expires: result.expires,
  }, 200, corsHeaders);
}

// ════════════════════════════════════════════════════════════
//  POST /unbind (Admin)
// ════════════════════════════════════════════════════════════
async function handleUnbind(body, corsHeaders) {
  const { admin_key, code, fp } = body;

  if (admin_key !== ADMIN_KEY) {
    return jsonResponse({ ok: false, error: '管理员密钥错误' }, 403, corsHeaders);
  }

  const codeKey = 'code:' + code;
  let codeData = await AUTH_CODES.get(codeKey, 'json');
  if (!codeData) {
    return jsonResponse({ ok: false, error: '激活码不存在' }, 404, corsHeaders);
  }

  if (fp) {
    codeData.devices = (codeData.devices || []).filter(d => d.fp !== fp);
  } else {
    codeData.devices = [];
  }

  await AUTH_CODES.put(codeKey, JSON.stringify(codeData));

  return jsonResponse({
    ok: true,
    devicesLeft: MAX_DEVICES - (codeData.devices || []).length,
  }, 200, corsHeaders);
}

// ════════════════════════════════════════════════════════════
//  Token 工具函数
// ════════════════════════════════════════════════════════════

async function signToken(fp, secret) {
  const expires = Date.now() + TOKEN_EXPIRES_MS;
  const payload = fp + '|' + secret + '|' + expires;
  const hashBuf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(payload));
  const hash = btoa(String.fromCharCode(...new Uint8Array(hashBuf)));
  return hash + '.' + fp + '.' + expires;
}

async function verifyToken(token, secret) {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return { ok: false };

    const [hash, fp, expiresStr] = parts;
    const expires = parseInt(expiresStr, 10);

    if (Date.now() > expires) return { ok: false };

    const payload = fp + '|' + secret + '|' + expires;
    const hashBuf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(payload));
    const expected = btoa(String.fromCharCode(...new Uint8Array(hashBuf)));

    if (hash.length !== expected.length) return { ok: false };
    let mismatch = 0;
    for (let i = 0; i < hash.length; i++) {
      mismatch |= hash.charCodeAt(i) ^ expected.charCodeAt(i);
    }
    if (mismatch !== 0) return { ok: false };

    return { ok: true, fp, expires };
  } catch {
    return { ok: false };
  }
}

function jsonResponse(data, status, headers) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  });
}
