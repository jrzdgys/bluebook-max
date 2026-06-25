// 蓝宝书Max · 设备绑定鉴权 Worker (v4)
// 改动：handleCodesCreate 存储 expiresAt；handleList 返回 expiresAt/createdAt；handleActivate 保留这两字段
// KV binding 名称: AUTH_CODES
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Max-Age': '86400',
};
// ADMIN_KEY: first try env var ADMIN_PASSWORD, then fallback to hardcoded
const ADMIN_KEY = (typeof ADMIN_PASSWORD !== 'undefined') ? ADMIN_PASSWORD : 'bbm-admin-2y0jPFwxk2MZQTfR';
const MAX_DEVICES = 2;

function json(data, status) {
  if (!status) status = 200;
  return new Response(JSON.stringify(data), {
    status: status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

async function handleActivate(body, request) {
  var code = (body.code || '').toUpperCase().trim();
  var fp = body.fp || '';
  if (!code || !fp) return json({ ok: false, error: '缺少激活码或设备指纹' });
  var ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  var sub;
  try { sub = JSON.parse(await AUTH_CODES.get(code) || '{}'); } catch (e) { sub = {}; }

  if (!sub.fingerprint) {
    sub = {
      fingerprint: fp,
      devices: [{ fingerprint: fp, ip: ip, lastSeen: Date.now() }],
      boundAt: Date.now(),
      lastAccess: Date.now(),
      ...(sub.createdAt ? { createdAt: sub.createdAt } : {}),
      ...(sub.expiresAt ? { expiresAt: sub.expiresAt } : {}),
      ...(sub.remark ? { remark: sub.remark } : {}),
    };
    await AUTH_CODES.put(code, JSON.stringify(sub));
    var tokenExpiry = sub.expiresAt ? Math.min(sub.expiresAt, Date.now() + 86400000 * 30) : (Date.now() + 86400000 * 30);
    var token = btoa(fp + '|' + Date.now() + '|bbm2026') + '.' + fp + '.' + tokenExpiry;
    return json({ ok: true, reason: 'bound', token: token, message: '绑定成功！' });
  }

  if (sub.fingerprint === fp || (sub.devices || []).some(function (d) { return d.fingerprint === fp; })) {
    sub.lastAccess = Date.now();
    await AUTH_CODES.put(code, JSON.stringify(sub));
    var token = btoa(fp + '|' + Date.now() + '|bbm2026') + '.' + fp + '.' + (Date.now() + 86400000 * 30);
    return json({ ok: true, reason: 'verified', token: token, message: '验证通过！' });
  }

  if ((sub.devices || []).length >= MAX_DEVICES)
    return json({ ok: false, error: '此码已绑定满' + MAX_DEVICES + '台设备，请联系管理员解绑' });

  sub.devices.push({ fingerprint: fp, ip: ip, lastSeen: Date.now() });
  sub.lastAccess = Date.now();
  await AUTH_CODES.put(code, JSON.stringify(sub));
  var token = btoa(fp + '|' + Date.now() + '|bbm2026') + '.' + fp + '.' + (Date.now() + 86400000 * 30);
  return json({ ok: true, reason: 'bound_new_device', token: token, message: '新设备绑定成功！' });
}

async function handleVerify(body) {
  var token = body.token || '';
  if (!token) return json({ ok: false, error: '缺少token' });
  var parts = token.split('.');
  if (parts.length < 3) return json({ ok: false, error: 'token格式错误' });
  var fp = parts[1];
  if (!fp) return json({ ok: false, error: 'token无效' });
  var cursor, found = null;
  try {
    do {
      var result = await AUTH_CODES.list({ cursor: cursor });
      for (var i = 0; i < result.keys.length; i++) {
        var d = JSON.parse(await AUTH_CODES.get(result.keys[i].name) || '{}');
        if (d.fingerprint === fp || (d.devices || []).some(function (x) { return x.fingerprint === fp; })) {
          found = result.keys[i].name;
          break;
        }
      }
      cursor = result.cursor;
    } while (cursor && !found);
  } catch (e) {}
  return found ? json({ ok: true, code: found }) : json({ ok: false, error: '未找到匹配的激活码' });
}

async function handleUnbind(body) {
  if (body.admin_key !== ADMIN_KEY) return json({ ok: false, error: '未授权' }, 403);
  var code = (body.code || '').toUpperCase().trim();
  if (!code) return json({ ok: false, error: '缺少激活码' });
  var sub;
  try { sub = JSON.parse(await AUTH_CODES.get(code) || '{}'); } catch (e) { sub = {}; }
  if (!sub.fingerprint && (!sub.devices || sub.devices.length === 0))
    return json({ ok: true, message: '该码暂无绑定', devicesLeft: 0 });
  await AUTH_CODES.delete(code);
  return json({ ok: true, message: '已完全解绑' });
}

async function handleList(body) {
  if (body.admin_key !== ADMIN_KEY) return json({ ok: false, error: '未授权' }, 403);
  var list = [], cursor;
  try {
    do {
      var result = await AUTH_CODES.list({ cursor: cursor });
      for (var i = 0; i < result.keys.length; i++) {
        var d = JSON.parse(await AUTH_CODES.get(result.keys[i].name) || '{}');
        list.push({
          code: result.keys[i].name,
          fingerprint: d.fingerprint ? d.fingerprint.substring(0, 20) + '...' : null,
          devices: (d.devices || []).length,
          boundAt: d.boundAt ? new Date(d.boundAt).toISOString() : null,
          lastAccess: d.lastAccess ? new Date(d.lastAccess).toISOString() : null,
          expiresAt: d.expiresAt ? new Date(d.expiresAt).toISOString() : null,
          remark: d.remark || '', createdAt: d.createdAt ? new Date(d.createdAt).toISOString() : null,
        });
      }
      cursor = result.cursor;
    } while (cursor);
  } catch (e) {}
  return json({ ok: true, codes: list });
}

async function handleCodesCreate(body) {
  if (body.admin_key !== ADMIN_KEY) return json({ ok: false, error: '未授权' }, 403);
  var codes = body.codes;
  if (!codes || !Array.isArray(codes) || !codes.length) return json({ ok: false, error: '缺少激活码列表' });
  var days = parseInt(body.days, 10) || 365;
  var expiresAt = Date.now() + days * 86400000;
  var created = [];
  for (var i = 0; i < codes.length; i++) {
    try {
      var existing = JSON.parse(await AUTH_CODES.get(codes[i]) || '{}');
      if (existing.fingerprint) continue;
      await AUTH_CODES.put(codes[i], JSON.stringify({ fingerprint: null, devices: [], remark: '', createdAt: Date.now(), expiresAt: expiresAt }));
      created.push(codes[i]);
    } catch (e) {}
  }
  return json({ ok: true, created: created, count: created.length, expiresAt: new Date(expiresAt).toISOString() });
}

async function handleCodesDelete(body) {
  if (body.admin_key !== ADMIN_KEY) return json({ ok: false, error: '未授权' }, 403);
  var code = (body.code || '').toUpperCase().trim();
  if (!code) return json({ ok: false, error: '缺少激活码' });
  await AUTH_CODES.delete(code);
  return json({ ok: true, message: '已删除' });
}

async function handleCodesRemark(body) {
      if (body.admin_key !== ADMIN_KEY) return json({ ok: false, error: '未授权' }, 403);
      var code = (body.code || '').toUpperCase().trim();
      if (!code) return json({ ok: false, error: '缺少激活码' });
      var remark = (body.remark || '').trim();
      var sub;
      try { sub = JSON.parse(await AUTH_CODES.get(code) || '{}'); } catch (e) { sub = {}; }
      sub.remark = remark;
      await AUTH_CODES.put(code, JSON.stringify(sub));
      return json({ ok: true, message: '备注已更新' });
    }

    addEventListener('fetch', function (event) {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS_HEADERS });
  if (request.method !== 'POST') return json({ error: 'Method not allowed' }, 405);
  var url = new URL(request.url);
  var path = url.pathname;
  try {
    var body = await request.json();
    switch (path) {
      case '/activate': return handleActivate(body, request);
      case '/verify': return handleVerify(body);
      case '/unbind': return handleUnbind(body);
      case '/list': return handleList(body);
      case '/codes/create': return handleCodesCreate(body);
      case '/codes/delete': return handleCodesDelete(body);
      case '/codes/remark': return handleCodesRemark(body);
      default: return json({ error: 'Not found' }, 404);
    }
  } catch (e) { return json({ error: e.message || 'Internal error' }, 500); }
}
