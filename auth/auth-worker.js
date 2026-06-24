/**
 * 蓝宝书Max · 设备绑定鉴权 Worker v1
 * ====================================
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
 * KV 结构:
 *   code:{CODE}  → { devices: [], expiresAt, createdAt }
 *   recover:{FP} → { code, lastIP, lastSeen }
 */

// ============================================================
//  引入 Crypto API (Cloudflare Workers 原生支持 Web Crypto)
// ============================================================

const TOKEN_EXPIRES_MS = 30 * 24 * 60 * 60 * 1000; // 30 天
const MAX_DEVICES = 2;
const RECOVER_DAYS = 30;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // CORS — 允许蓝宝书Max域名
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
          return handleActivate(body, env, corsHeaders, request);
        case '/verify':
          return handleVerify(body, env, corsHeaders);
        case '/unbind':
          return handleUnbind(body, env, corsHeaders);
        case '/list':
          return handleList(body, env, corsHeaders);
        case '/info':
          return handleInfo(body, env, corsHeaders);
        case '/codes/create':
          return handleCreateCode(body, env, corsHeaders);
        default:
          return jsonResponse({ error: 'Not found' }, 404, corsHeaders);
      }
    } catch (err) {
      return jsonResponse({ error: 'Internal error' }, 500, corsHeaders);
    }
  },
};

// ============================================================
//  POST /activate
// ============================================================
async function handleActivate(body, env, corsHeaders, request) {
  const { code, fp } = body;
  if (!code || !fp) {
    return jsonResponse({ ok: false, error: '缺少激活码或设备指纹' }, 400, corsHeaders);
  }

  const codeKey = `code:${code}`;
  let codeData = await env.AUTH_CODES.get(codeKey, 'json');

  // 码不存在
  if (!codeData) {
    return jsonResponse({ ok: false, error: '无效的激活码' }, 403, corsHeaders);
  }

  // 码已过期
  if (Date.now() > new Date(codeData.expiresAt).getTime()) {
    return jsonResponse({ ok: false, error: '激活码已过期' }, 403, corsHeaders);
  }

  const devices = codeData.devices || [];

  // === 情况1: 首次激活 ===
  if (devices.length === 0) {
    const token = await signToken(fp, env.TOKEN_SECRET);
    const deviceInfo = {
      fp,
      activatedAt: new Date().toISOString(),
      lastSeen: new Date().toISOString(),
    };
    devices.push(deviceInfo);
    await env.AUTH_CODES.put(codeKey, JSON.stringify({
      ...codeData,
      devices,
      used: true,
    }));
    // 写入 recover 记录
    await env.AUTH_CODES.put(`recover:${fp}`, JSON.stringify({
      code,
      lastIP: _clientIP || "",
      lastSeen: new Date().toISOString(),
    }));
    return jsonResponse({
      ok: true,
      token,
      expires: Date.now() + TOKEN_EXPIRES_MS,
      expiresAt: codeData.expiresAt,
      devicesLeft: MAX_DEVICES - devices.length,
    }, 200, corsHeaders);
  }

  // === 情况2: 已在设备列表中（清缓存恢复） ===
  const existingDevice = devices.find(d => d.fp === fp);
  if (existingDevice) {
    const token = await signToken(fp, env.TOKEN_SECRET);
    existingDevice.lastSeen = new Date().toISOString();
    await env.AUTH_CODES.put(codeKey, JSON.stringify({ ...codeData, devices }));
    return jsonResponse({
      ok: true,
      token,
      expires: Date.now() + TOKEN_EXPIRES_MS,
      expiresAt: codeData.expiresAt,
      devicesLeft: MAX_DEVICES - devices.length,
      recovered: true,
    }, 200, corsHeaders);
  }

  // === 情况3: 设备已满 ===
  if (devices.length >= MAX_DEVICES) {
    // 检查清缓存恢复条件：同IP + <30天
        /* _clientIP passed as parameter */
    const lastDevice = devices[devices.length - 1];
    const daysSinceLast = (Date.now() - new Date(lastDevice.lastSeen).getTime())
      / (24 * 60 * 60 * 1000);

    if (daysSinceLast < RECOVER_DAYS) {
      return jsonResponse({
        ok: false,
        error: `已达设备上限(${MAX_DEVICES}台)，请联系管理员解绑`,
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

    const token = await signToken(fp, env.TOKEN_SECRET);
    await env.AUTH_CODES.put(codeKey, JSON.stringify({ ...codeData, devices }));
    return jsonResponse({
      ok: true,
      token,
      expires: Date.now() + TOKEN_EXPIRES_MS,
      expiresAt: codeData.expiresAt,
      devicesLeft: 0,
      recovered: true,
    }, 200, corsHeaders);
  }

  // === 情况4: 还有设备名额 → 绑新设备 ===
  const token = await signToken(fp, env.TOKEN_SECRET);
  const newDevice = {
    fp,
    activatedAt: new Date().toISOString(),
    lastSeen: new Date().toISOString(),
  };
  devices.push(newDevice);
  await env.AUTH_CODES.put(codeKey, JSON.stringify({ ...codeData, devices }));
  await env.AUTH_CODES.put(`recover:${fp}`, JSON.stringify({
    code,
    lastIP: _clientIP || "",
    lastSeen: new Date().toISOString(),
  }));
  return jsonResponse({
    ok: true,
    token,
    expires: Date.now() + TOKEN_EXPIRES_MS,
    devicesLeft: MAX_DEVICES - devices.length,
  }, 200, corsHeaders);
}

// ============================================================
//  POST /verify
//  自包含 token 验证，不读 KV
// ============================================================
async function handleVerify(body, env, corsHeaders) {
  const { token } = body;
  if (!token) {
    return jsonResponse({ ok: false, error: '缺少 token' }, 400, corsHeaders);
  }

  const result = await verifyToken(token, env.TOKEN_SECRET);
  if (!result.ok) {
    return jsonResponse({ ok: false, error: 'token 无效或已过期' }, 403, corsHeaders);
  }

  return jsonResponse({
    ok: true,
    fp: result.fp,
    expires: result.expires,
  }, 200, corsHeaders);
}

// ============================================================
//  POST /unbind  (Admin)
// ============================================================
async function handleUnbind(body, env, corsHeaders) {
  const { admin_key, code, fp } = body;

  if (admin_key !== env.ADMIN_KEY) {
    return jsonResponse({ ok: false, error: '管理员密钥错误' }, 403, corsHeaders);
  }

  const codeKey = `code:${code}`;
  let codeData = await env.AUTH_CODES.get(codeKey, 'json');
  if (!codeData) {
    return jsonResponse({ ok: false, error: '激活码不存在' }, 404, corsHeaders);
  }

  if (fp) {
    // 解绑指定设备
    codeData.devices = (codeData.devices || []).filter(d => d.fp !== fp);
  } else {
    // 解绑全部设备
    codeData.devices = [];
  }

  await env.AUTH_CODES.put(codeKey, JSON.stringify(codeData));

  return jsonResponse({
    ok: true,
    devicesLeft: MAX_DEVICES - (codeData.devices || []).length,
  }, 200, corsHeaders);
}

// ============================================================
//  POST /list  (Admin — 列出全部激活码)
// ============================================================
async function handleList(body, env, corsHeaders) {
  const { admin_key } = body;
  if (admin_key !== env.ADMIN_KEY) {
    return jsonResponse({ ok: false, error: '管理员密钥错误' }, 403, corsHeaders);
  }

  const codeList = [];
  let cursor = undefined;
  do {
    const listResult = await env.AUTH_CODES.list({ prefix: 'code:', cursor, limit: 100 });
    for (const key of listResult.keys) {
      const codeData = await env.AUTH_CODES.get(key.name, 'json');
      codeList.push({
        code: key.name.replace('code:', ''),
        devices: (codeData?.devices || []).length,
        maxDevices: MAX_DEVICES,
        expiresAt: codeData?.expiresAt || null,
        createdAt: codeData?.createdAt || null,
        used: codeData?.used || false,
      });
    }
    cursor = listResult.cursor;
  } while (cursor);

  return jsonResponse({ ok: true, codes: codeList }, 200, corsHeaders);
}

// ============================================================
//  POST /info  (Admin — 查询单个激活码详情)
// ============================================================
async function handleInfo(body, env, corsHeaders) {
  const { admin_key, code } = body;
  if (admin_key !== env.ADMIN_KEY) {
    return jsonResponse({ ok: false, error: '管理员密钥错误' }, 403, corsHeaders);
  }
  if (!code) {
    return jsonResponse({ ok: false, error: '缺少激活码' }, 400, corsHeaders);
  }

  const codeKey = 'code:' + code;
  const codeData = await env.AUTH_CODES.get(codeKey, 'json');
  if (!codeData) {
    return jsonResponse({ ok: false, error: '激活码不存在' }, 404, corsHeaders);
  }

  return jsonResponse({
    ok: true,
    code,
    devices: codeData.devices || [],
    expiresAt: codeData.expiresAt,
    createdAt: codeData.createdAt,
  }, 200, corsHeaders);
}


// ============================================================
//  POST /codes/create  (Admin — 批量生成激活码)
// ============================================================
async function handleCreateCode(body, env, corsHeaders) {
  const { admin_key, codes, days } = body;
  if (admin_key !== env.ADMIN_KEY) {
    return jsonResponse({ ok: false, error: '管理员密钥错误' }, 403, corsHeaders);
  }
  if (!codes || !Array.isArray(codes) || codes.length === 0) {
    return jsonResponse({ ok: false, error: '缺少激活码列表' }, 400, corsHeaders);
  }

  const expiresAt = new Date(Date.now() + (days || 365) * 24 * 60 * 60 * 1000).toISOString();
  const createdAt = new Date().toISOString();
  let created = 0;

  for (const code of codes) {
    const codeKey = 'code:' + code;
    const existing = await env.AUTH_CODES.get(codeKey, 'json');
    if (existing) continue; // 跳过已存在的码
    await env.AUTH_CODES.put(codeKey, JSON.stringify({
      devices: [],
      expiresAt,
      createdAt,
    }));
    created++;
  }

  return jsonResponse({
    ok: true,
    created,
    expiresAt,
    total: codes.length,
  }, 200, corsHeaders);
}

// ============================================================
//  Token 工具函数
// ============================================================

async function signToken(fp, secret) {
  const expires = Date.now() + TOKEN_EXPIRES_MS;
  const payload = `${fp}|${secret}|${expires}`;
  const hashBuf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(payload));
  const hash = btoa(String.fromCharCode(...new Uint8Array(hashBuf)));
  return `${hash}.${fp}.${expires}`;
}

async function verifyToken(token, secret) {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return { ok: false };

    const [hash, fp, expiresStr] = parts;
    const expires = parseInt(expiresStr, 10);

    // 过期检查
    if (Date.now() > expires) return { ok: false };

    // hash 校验
    const payload = `${fp}|${secret}|${expires}`;
    const hashBuf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(payload));
    const expected = btoa(String.fromCharCode(...new Uint8Array(hashBuf)));

    // 常数时间比较防止时序攻击
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

// ============================================================
//  辅助函数
// ============================================================

function jsonResponse(data, status, headers) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  });
}
