/**
     * 蓝宝书Max · 设备绑定鉴权系统 v3
     * =============================
     * 一人一号，绑定≤2台设备。
     * Canvas 指纹 + 容差匹配（兼容 iOS Safari）。
     * 清缓存恢复机制：同码+同IP+30天内自动识别。
     */

    // ===== 配置 =====
    const WORKER_URL    = "https://bluebook-auth.bluebookmax.workers.dev";
    const AUTH_KEY      = "bbm_auth_token";
    const FP_CACHE_KEY  = "bbm_fp_cache";
    const EXPIRES_KEY   = "bbm_expires_at";

    // ===== 设备指纹采集（移动端优化版）=====
    async function collectFingerprint() {
      const nav = {
        ua: navigator.userAgent,
        platform: navigator.platform,
        lang: navigator.language,
        cores: navigator.hardwareConcurrency || 4,
        vendor: navigator.vendor || '',
      };
      const scr = { w: screen.width, h: screen.height, dpr: window.devicePixelRatio || 1, cd: screen.colorDepth || 24 };
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const canvasHash = await getCanvasHash();
      const stableParts = [nav.ua, nav.platform, nav.lang, scr.w, scr.h, scr.dpr, tz].join('|||');
      const fp = await sha256(stableParts + '|||' + canvasHash);
      return { hash: fp, canvas: canvasHash, stable: stableParts, ua: nav.ua };
    }

    // Canvas 指纹 - 简化版，不依赖 rAF
    function getCanvasHash() {
      return new Promise(function(resolve) {
        var timer = setTimeout(function() { resolve('canvas-timeout-' + Date.now()); }, 3000);
        try {
          var c = document.createElement('canvas');
          c.width = 200; c.height = 50;
          var ctx = c.getContext('2d');
          if (!ctx) { clearTimeout(timer); resolve('no-ctx-' + Date.now()); return; }
          ctx.textBaseline = 'alphabetic'; ctx.font = '14px Arial,sans-serif';
          ctx.fillStyle = '#1D1D1F'; ctx.fillText('BluebookMax', 10, 30);
          ctx.fillStyle = '#0071E3'; ctx.fillRect(10, 10, 40, 20);
          try {
            var data = c.toDataURL();
            clearTimeout(timer);
            resolve(data ? data.substring(50, 250) : 'empty-' + Date.now());
          } catch(e) { clearTimeout(timer); resolve('canvas-error-' + Date.now()); }
        } catch(e) { clearTimeout(timer); resolve('canvas-exception-' + Date.now()); }
      });
    }

    async function sha256(str) {
      if (!crypto || !crypto.subtle || !crypto.subtle.digest) {
        var h = 0; for (var i = 0; i < str.length; i++) { h = ((h << 5) - h) + str.charCodeAt(i); h |= 0; }
        return 'fp_' + Math.abs(h).toString(16);
      }
      try {
        var buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
        return Array.from(new Uint8Array(buf)).map(function(b) { return b.toString(16).padStart(2, '0'); }).join('');
      } catch(e) {
        var h = 0; for (var i = 0; i < str.length; i++) { h = ((h << 5) - h) + str.charCodeAt(i); h |= 0; }
        return 'fp_' + Math.abs(h).toString(16);
      }
    }

    // ===== 动态注入CSS =====
    function _injectAuthCSS() {
      if (document.getElementById('bbm-auth-styles')) return;
      var s = document.createElement('style'); s.id = 'bbm-auth-styles';
      s.textContent = '.auth-overlay{position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.5);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;animation:pwFade .3s ease}' +
        '.auth-modal{background:rgba(255,255,255,.95);backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);border-radius:20px;padding:40px 32px;max-width:380px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.2);text-align:center;position:relative}' +
        '.auth-icon{font-size:48px;margin-bottom:12px}.auth-modal h2{font-size:22px;font-weight:700;margin-bottom:6px}.auth-desc{font-size:14px;color:#86868B;margin-bottom:24px}' +
        '.auth-input{width:100%;padding:14px 18px;border:2px solid #E5E5EA;border-radius:14px;font-size:18px;text-align:center;letter-spacing:2px;font-family:"SF Mono",Menlo,monospace;outline:none;transition:border-color .2s;box-sizing:border-box}' +
        '.auth-input:focus{border-color:#0071E3}.auth-btn{width:100%;padding:14px;margin-top:14px;background:#0071E3;color:#fff;border:none;border-radius:14px;font-size:16px;font-weight:600;cursor:pointer;transition:all .2s;font-family:inherit}' +
        '.auth-btn:hover{background:#0060C0}.auth-btn:disabled{opacity:.5;cursor:not-allowed}.auth-error{color:#C4433A;font-size:13px;margin-top:12px;min-height:20px}' +
        '.auth-recover{font-size:12px;color:#AEAEB2;margin-top:16px;line-height:1.5}.auth-footer{font-size:11px;color:#AEAEB2;margin-top:24px;line-height:1.4}' +
        '.auth-close{position:absolute;top:12px;right:14px;background:none;border:none;font-size:22px;color:#AEAEB2;cursor:pointer;padding:4px 12px;border-radius:8px;line-height:1;transition:all .15s;font-family:inherit}' +
        '.auth-close:hover{background:rgba(0,0,0,.05);color:#1D1D1F}@keyframes pwFade{from{opacity:0}to{opacity:1}}';
      document.head.appendChild(s);
    }

    // ===== Paywall =====
    const Paywall = {
      isAuthenticated() {
        var t = localStorage.getItem(AUTH_KEY);
        if (!t) return false;
        var parts = t.split('.');
        if (parts.length < 3) return false;
        var expires = parseInt(parts[2], 10);
        if (isNaN(expires)) return false;
        if (expires < Date.now() - 86400000 * 30) return false;
        return true;
      },
      getToken() { return localStorage.getItem(AUTH_KEY); },

      async activate(code) {
        var fpData;
        try { fpData = await collectFingerprint(); } catch(e) { return { ok: false, error: '设备指纹采集失败' }; }
        var controller = new AbortController();
        var timeout = setTimeout(function() { controller.abort(); }, 8000);
        try {
          var res = await fetch(WORKER_URL + '/activate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code.toUpperCase(), fp: fpData.hash, canvas: fpData.canvas, stable: fpData.stable, ua: fpData.ua }),
            signal: controller.signal,
          });
          clearTimeout(timeout);
          var data = await res.json();
          if (data.ok && data.token) {
            try {
              localStorage.setItem(AUTH_KEY, data.token);
              localStorage.setItem(FP_CACHE_KEY, JSON.stringify({ hash: fpData.hash, canvas: fpData.canvas, stable: fpData.stable }));
              var exp = parseInt(data.token.split('.')[2], 10);
              if (!isNaN(exp)) localStorage.setItem(EXPIRES_KEY, String(exp));
            } catch {}
          }
          return data;
        } catch(e) {
          clearTimeout(timeout);
          if (e.name === 'AbortError') return { ok: false, error: '请求超时，请检查网络后重试' };
          return { ok: false, error: '网络错误，请检查网络后重试' };
        }
      },

      logout() { localStorage.removeItem(AUTH_KEY); localStorage.removeItem(FP_CACHE_KEY); localStorage.removeItem(EXPIRES_KEY); },

      showActivationModal(onSuccess) {
        var overlay = document.getElementById('auth-overlay');
        if (overlay) { overlay.style.display = 'flex'; var input = document.getElementById('auth-code'); if (input) setTimeout(function() { input.focus(); }, 200); return; }
        this._createModal(onSuccess);
      },

      _createModal(onSuccess) {
        _injectAuthCSS();
        var old = document.getElementById('auth-overlay'); if (old) old.remove();
        var overlay = document.createElement('div'); overlay.id = 'auth-overlay'; overlay.className = 'auth-overlay';
        overlay.innerHTML = '<div class="auth-modal"><button class="auth-close" id="auth-close-btn">×</button><div class="auth-icon">🔑</div><h2>访问码激活</h2><p class="auth-desc">请输入您在知识星球获取的访问码</p><input class="auth-input" id="auth-code" placeholder="输入访问码" maxlength="20" autocomplete="off" autocorrect="off" spellcheck="false"><button class="auth-btn" id="auth-btn">激活账号</button><div class="auth-error" id="auth-error"></div><div class="auth-recover">每个访问码可绑定 2 台设备</div><div class="auth-footer">尚未加入？前往 <a href="https://t.zsxq.com/6iVvp" target="_blank" style="color:#0071E3;text-decoration:none;font-weight:600">知识星球 · 蓝宝书Max</a></div></div>';
        document.body.appendChild(overlay);
        var input = document.getElementById('auth-code');
        var btn = document.getElementById('auth-btn');
        var doActivate = function() {
          var code = input.value.trim(); if (!code) { showError('请输入激活码'); return; }
          btn.disabled = true; btn.textContent = '验证中...'; clearError();
          Paywall.activate(code).then(function(result) {
            if (result.ok) { hideModal(); if (onSuccess) onSuccess(); else window.location.reload(); }
            else { showError(result.error || '激活失败，请检查激活码'); btn.disabled = false; btn.textContent = '激活账号'; if (input) input.focus(); }
          }).catch(function() { showError('系统错误，请稍后重试'); btn.disabled = false; btn.textContent = '激活账号'; });
        };
        btn.addEventListener('click', doActivate);
        input.addEventListener('keydown', function(e) { if (e.key === 'Enter') doActivate(); });
        input.addEventListener('input', function() { clearError(); });
        setTimeout(function() { input.focus(); }, 200);
        function showError(msg) { var el = document.getElementById('auth-error'); if (el) el.textContent = msg; }
        function clearError() { var el = document.getElementById('auth-error'); if (el) el.textContent = ''; }
        function hideModal() { var o = document.getElementById('auth-overlay'); if (o) o.style.display = 'none'; }
        document.getElementById('auth-close-btn').addEventListener('click', hideModal);
      },
      closeAuthModal() { var o = document.getElementById('auth-overlay'); if (o) o.style.display = 'none'; },
      showLogin() { this.showActivationModal(null); },
      getExpiryDate() {
        var expiresAt = localStorage.getItem(EXPIRES_KEY); if (!expiresAt) return null;
        var date = new Date(parseInt(expiresAt, 10)); return isNaN(date.getTime()) ? null : date;
      },
      formatExpiry() {
        var date = this.getExpiryDate(); if (!date) return '';
        return date.getFullYear() + '/' + String(date.getMonth()+1).padStart(2,'0') + '/' + String(date.getDate()).padStart(2,'0');
      },
      unlockBadge() {
        var expiry = this.formatExpiry();
        var text = expiry ? '✓ 已订阅 · 有效期至 ' + expiry : '✓ 已订阅';
        return '<span class="unlock-badge">' + text + '</span>';
      },
    };

    // ===== 页面初始化检测 =====
    document.addEventListener('DOMContentLoaded', function() {
      var needsAuth = document.documentElement.getAttribute('data-paywall') === 'true';
      if (!needsAuth) return;
      if (Paywall.isAuthenticated()) { document.documentElement.classList.add('bb-authenticated'); return; }
      Paywall.showActivationModal(function() { window.location.reload(); });
    });

    // ===== 导航页认证状态更新 =====
    window.__bbmRefreshAuth = function() {
      var isAuth = Paywall.isAuthenticated();
      var badge = document.getElementById('auth-badge');
      if (badge) badge.innerHTML = isAuth ? Paywall.unlockBadge() : '';
      var btn = document.getElementById('btn-nav-login');
      if (btn) { btn.textContent = isAuth ? '已订阅' : '订阅'; btn.style.background = isAuth ? 'rgba(52,199,89,.1)' : 'rgba(0,113,227,.08)'; btn.style.color = isAuth ? '#34C759' : '#0071E3'; }
    };
    