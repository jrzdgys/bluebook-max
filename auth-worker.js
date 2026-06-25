// 蓝宝书Max · 设备绑定鉴权 Worker (v2)
    // KV binding: SUBS (在 Cloudflare Dashboard 配置)
    // 部署: 粘贴此代码到 worker.js 后点"保存并部署"

    const CORS_HEADERS = {
      'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Max-Age': '86400',
    };
    const ADMIN_KEY = 'bbmax-admin-2026';
    const MAX_DEVICES = 2;

    function json(data, status = 200) {
      return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', ...CORS_HEADERS } });
    }

    export default {
      async fetch(request, env) {
        if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS_HEADERS });
        if (request.method !== 'POST') return json({ error: 'Method not allowed' }, 405);
        const url = new URL(request.url); const path = url.pathname;
        try {
          const body = await request.json();
          switch (path) {
            case '/activate': return handleActivate(body, env, request);
            case '/verify': return handleVerify(body, env, request);
            case '/unbind': return handleUnbind(body, env);
            case '/list': return handleList(body, env);
            case '/codes/create': return handleCodesCreate(body, env);
            case '/codes/delete': return handleCodesDelete(body, env);
            default: return json({ error: 'Not found' }, 404);
          }
        } catch (e) { return json({ error: e.message || 'Internal error' }, 500); }
      },
    };

    async function handleActivate(body, env, request) {
      const code = (body.code || '').toUpperCase().trim(); const fp = body.fp || '';
      if (!code || !fp) return json({ ok: false, error: '缺少激活码或设备指纹' });
      const ip = request.headers.get('CF-Connecting-IP') || 'unknown';

      try { var sub = JSON.parse(await env.SUBS.get(code) || '{}'); } catch { sub = {}; }

      // New bind
      if (!sub.fingerprint) {
        sub = { fingerprint: fp, devices: [{ fingerprint: fp, ip, lastSeen: Date.now() }], boundAt: Date.now(), lastAccess: Date.now() };
        await env.SUBS.put(code, JSON.stringify(sub));
        const token = btoa(fp + '|' + Date.now() + '|bbm2026') + '.' + fp + '.' + Date.now();
        return json({ ok: true, reason: 'bound', token, message: '绑定成功！' });
      }

      // Same device
      if (sub.fingerprint === fp || (sub.devices || []).some(d => d.fingerprint === fp)) {
        sub.lastAccess = Date.now(); await env.SUBS.put(code, JSON.stringify(sub));
        const token = btoa(fp + '|' + Date.now() + '|bbm2026') + '.' + fp + '.' + Date.now();
        return json({ ok: true, reason: 'verified', token, message: '验证通过！' });
      }

      // Device limit
      if ((sub.devices || []).length >= MAX_DEVICES) {
        return json({ ok: false, error: '此码已绑定满' + MAX_DEVICES + '台设备，请联系管理员解绑' });
      }

      // New device
      sub.devices.push({ fingerprint: fp, ip, lastSeen: Date.now() });
      sub.lastAccess = Date.now(); await env.SUBS.put(code, JSON.stringify(sub));
      const token = btoa(fp + '|' + Date.now() + '|bbm2026') + '.' + fp + '.' + Date.now();
      return json({ ok: true, reason: 'bound_new_device', token, message: '新设备绑定成功！' });
    }

    async function handleVerify(body, env, request) {
      const token = body.token || ''; if (!token) return json({ ok: false, error: '缺少token' });
      const parts = token.split('.'); if (parts.length < 3) return json({ ok: false, error: 'token格式错误' });
      const fp = parts[1]; if (!fp) return json({ ok: false, error: 'token无效' });

      // Scan KV for matching fp
      let cursor; let found = null;
      try {
        do {
          const result = await env.SUBS.list({ cursor });
          for (const key of result.keys) {
            const d = JSON.parse(await env.SUBS.get(key.name) || '{}');
            if (d.fingerprint === fp || (d.devices || []).some(x => x.fingerprint === fp)) { found = key.name; break; }
          }
          cursor = result.cursor;
        } while (cursor && !found);
      } catch {}

      return found ? json({ ok: true, code: found }) : json({ ok: false, error: '未找到匹配的激活码' });
    }

    async function handleUnbind(body, env) {
      if (body.admin_key !== ADMIN_KEY) return json({ ok: false, error: '未授权' }, 403);
      const code = (body.code || '').toUpperCase().trim(); if (!code) return json({ ok: false, error: '缺少激活码' });
      const deviceFp = body.deviceFp;
      try { var sub = JSON.parse(await env.SUBS.get(code) || '{}'); } catch { sub = {}; }
      if (!sub.fingerprint) return json({ ok: false, error: '激活码不存在' });

      if (deviceFp) {
        sub.devices = (sub.devices || []).filter(d => d.fingerprint !== deviceFp);
        if (sub.devices.length === 0) { sub.fingerprint = null; sub.boundAt = null; }
        else if (sub.fingerprint === deviceFp) sub.fingerprint = sub.devices[0].fingerprint;
        await env.SUBS.put(code, JSON.stringify(sub));
        return json({ ok: true, message: '设备已解绑', devices: sub.devices.length });
      }
      await env.SUBS.delete(code);
      return json({ ok: true, message: '已完全解绑' });
    }

    async function handleList(body, env) {
      if (body.admin_key !== ADMIN_KEY) return json({ ok: false, error: '未授权' }, 403);
      const list = []; let cursor;
      try {
        do {
          const result = await env.SUBS.list({ cursor });
          for (const key of result.keys) {
            const d = JSON.parse(await env.SUBS.get(key.name) || '{}');
            list.push({ code: key.name, fingerprint: d.fingerprint ? (d.fingerprint.substring(0,20)+'...') : null, devices: (d.devices || []).length, boundAt: d.boundAt ? new Date(d.boundAt).toISOString() : null, lastAccess: d.lastAccess ? new Date(d.lastAccess).toISOString() : null });
          }
          cursor = result.cursor;
        } while (cursor);
      } catch {}
      return json({ ok: true, codes: list });
    }

    async function handleCodesCreate(body, env) {
      if (body.admin_key !== ADMIN_KEY) return json({ ok: false, error: '未授权' }, 403);
      const { codes } = body; if (!codes || !Array.isArray(codes) || !codes.length) return json({ ok: false, error: '缺少激活码列表' });
      const created = [];
      for (const code of codes) {
        try {
          const existing = JSON.parse(await env.SUBS.get(code) || '{}');
          if (existing.fingerprint) continue;
          await env.SUBS.put(code, JSON.stringify({ fingerprint: null, devices: [], createdAt: Date.now() }));
          created.push(code);
        } catch {}
      }
      return json({ ok: true, created, count: created.length });
    }

    async function handleCodesDelete(body, env) {
      if (body.admin_key !== ADMIN_KEY) return json({ ok: false, error: '未授权' }, 403);
      const code = (body.code || '').toUpperCase().trim(); if (!code) return json({ ok: false, error: '缺少激活码' });
      await env.SUBS.delete(code);
      return json({ ok: true, message: '已删除' });
    }
    