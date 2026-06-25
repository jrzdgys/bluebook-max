/**
 * 蓝宝书Max · 设备绑定鉴权系统
 * =============================
 *
 * 一人一号，绑定≤2台设备。
 * Token 自包含（纯计算验证，不读 KV）。
 * Canvas 指纹 + 容差匹配（兼容 iOS Safari）。
 * 清缓存恢复机制：同码+同IP+30天内自动识别。
 *
 * 部署前配置：
 *   1. 部署 Cloudflare Worker (见 auth-worker.js)
 *   2. 将 WORKER_URL 改为实际 Worker 地址
 */

// ===== 配置 =====
const WORKER_URL    = "https://bluebook-auth.bluebookmax.workers.dev";
const AUTH_KEY      = "bbm_auth_token";
const FP_CACHE_KEY  = "bbm_fp_cache";
const EXPIRES_KEY    = "bbm_expires_at";

// ===== 设备指纹采集 =====
// 主指纹：navigator + screen + timezone（稳定）
// 辅助指纹：Canvas（iOS Safari 可能变化，用于容差匹配）
async function collectFingerprint() {
  const nav = {
    ua: navigator.userAgent,
    platform: navigator.platform,
    lang: navigator.language,
    cores: navigator.hardwareConcurrency || 4,
    mem: navigator.deviceMemory || 0,
    pdf: navigator.pdfViewerEnabled || false,
    vendor: navigator.vendor || '',
  };

  const scr = {
    w: screen.width,
    h: screen.height,
    dpr: window.devicePixelRatio || 1,
    cd: screen.colorDepth || 24,
  };

  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  // Canvas 指纹（兼容 iOS）
  const canvasHash = await getCanvasHash();

  // 组合主关键串（用于精确匹配）
  const stableParts = [
    nav.ua,
    nav.platform,
    nav.lang,
    scr.w, scr.h,
    scr.dpr,
    tz,
  ].join('|||');

  // 完整指纹 hash
  const fp = await sha256(stableParts + '|||' + canvasHash);

  return {
    hash: fp,
    canvas: canvasHash,      // 单独存，用于容差匹配
    stable: stableParts,      // 存用于恢复时的快速匹配
  };
}

// Canvas 指纹（简化，兼容 iOS 隐私模式）
function getCanvasHash() {
  // iOS Safari 隐私模式下 canvas.toDataURL() 可能卡死
  // 使用 Promise.race 加 3 秒超时防护
  return new Promise(function(resolve) {
    var timedOut = false;
    var timer = setTimeout(function() {
      timedOut = true;
      resolve('canvas-timeout');
    }, 3000);

    try {
      var c = document.createElement('canvas');
      c.width = 200; c.height = 50;
      var ctx = c.getContext('2d');
      if (!ctx) { clearTimeout(timer); resolve('no-canvas'); return; }

      ctx.textBaseline = 'alphabetic';
      ctx.font = '16px "Arial",sans-serif';
      ctx.fillStyle = '#1D1D1F';
      ctx.fillText('蓝宝书Max', 10, 30);
      ctx.fillStyle = '#0071E3';
      ctx.fillRect(10, 10, 40, 20);

      // 使用 requestAnimationFrame 来避免阻塞主线程
      requestAnimationFrame(function() {
        if (timedOut) return;
        try {
          var data = c.toDataURL();
          clearTimeout(timer);
          if (data.length < 100) resolve('canvas-blocked');
          else resolve(data.substring(50, 250));
        } catch(e) {
          clearTimeout(timer);
          resolve('canvas-error');
        }
      });
    } catch(e) {
      clearTimeout(timer);
      resolve('canvas-error');
    }
  });
}

// SHA-256 hash
async function sha256(str) {
      if (!crypto || !crypto.subtle || !crypto.subtle.digest) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
          hash = ((hash << 5) - hash) + str.charCodeAt(i);
          hash |= 0;
        }
        return 'fp_' + Math.abs(hash).toString(16);
      }
      try {
        const buf = await crypto.subtle.digest('SHA-256',
          new TextEncoder().encode(str));
        return Array.from(new Uint8Array(buf))
          .map(b => b.toString(16).padStart(2, '0')).join('');
      } catch(e) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
          hash = ((hash << 5) - hash) + str.charCodeAt(i);
          hash |= 0;
        }
        return 'fp_' + Math.abs(hash).toString(16);
      }
    }


// ===== 动态注入认证弹窗CSS（确保独立于index.html样式） =====
function _injectAuthCSS() {
  if (document.getElementById('bbm-auth-styles')) return;
  var style = document.createElement('style');
  style.id = 'bbm-auth-styles';
  style.textContent =
    '.auth-overlay{' +
    'position:fixed;inset:0;z-index:9999;' +
    'background:rgba(0,0,0,.5);' +
    'backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);' +
    'display:flex;align-items:center;justify-content:center;' +
    'animation:pwFade .3s ease' +
    '}' +
    '.auth-modal{' +
    'background:rgba(255,255,255,.95);' +
    'backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);' +
    'border-radius:20px;padding:40px 32px;' +
    'max-width:380px;width:90%;' +
    'box-shadow:0 20px 60px rgba(0,0,0,.2);' +
    'text-align:center;position:relative' +
    '}' +
    '.auth-icon{font-size:48px;margin-bottom:12px}' +
    '.auth-modal h2{font-size:22px;font-weight:700;margin-bottom:6px}' +
    '.auth-desc{font-size:14px;color:#86868B;margin-bottom:24px}' +
    '.auth-input{' +
    'width:100%;padding:14px 18px;' +
    'border:2px solid #E5E5EA;border-radius:14px;' +
    'font-size:18px;text-align:center;letter-spacing:2px;' +
    'font-family:"SF Mono",Menlo,monospace;' +
    'outline:none;transition:border-color .2s;' +
    'box-sizing:border-box' +
    '}' +
    '.auth-input:focus{border-color:#0071E3}' +
    '.auth-btn{' +
    'width:100%;padding:14px;margin-top:14px;' +
    'background:#0071E3;color:#fff;border:none;' +
    'border-radius:14px;font-size:16px;font-weight:600;' +
    'cursor:pointer;transition:all .2s;font-family:inherit' +
    '}' +
    '.auth-btn:hover{background:#0060C0}' +
    '.auth-btn:disabled{opacity:.4;cursor:not-allowed}' +
    '.auth-error{color:#C4433A;font-size:13px;margin-top:12px;min-height:20px}' +
    '.auth-recover{font-size:12px;color:#AEAEB2;margin-top:16px;line-height:1.5}' +
    '.auth-footer{font-size:11px;color:#AEAEB2;margin-top:24px;line-height:1.4}' +
    '.auth-close{' +
    'position:absolute;top:12px;right:14px;' +
    'background:none;border:none;font-size:22px;' +
    'color:#AEAEB2;cursor:pointer;padding:4px 12px;' +
    'border-radius:8px;line-height:1;' +
    'transition:all .15s;font-family:inherit' +
    '}' +
    '.auth-close:hover{background:rgba(0,0,0,.05);color:#1D1D1F}' +
    '@keyframes pwFade{from{opacity:0}to{opacity:1}}';
  document.head.appendChild(style);
}


// ===== Paywall 对象（与 index.html 的调用点兼容） =====
const Paywall = {

  // ---------- 鉴权 ----------

  isAuthenticated() {
    const t = localStorage.getItem(AUTH_KEY);
    if (!t) return false;
    // 简单格式检查
    const parts = t.split('.');
    return parts.length === 3 && parts[1].length > 0;
  },

  getToken() {
    return localStorage.getItem(AUTH_KEY);
  },

  // ---------- 验证 token（自包含，不请求 Worker） ----------
  // 前端只做基础格式校验，真正的签名验证由 Worker 完成
  // 这里返回 token 中的过期时间用于本地缓存判断
  getTokenExpiry() {
    try {
      const t = this.getToken();
      if (!t) return 0;
      const expires = parseInt(t.split('.')[2], 10);
      return isNaN(expires) ? 0 : expires;
    } catch { return 0; }
  },

  isTokenExpired() {
    return Date.now() > this.getTokenExpiry();
  },

  // ---------- 远程验证（调用 Worker /verify） ----------

  async verifyWithWorker() {
        const token = this.getToken();
        if (!token) return { ok: false, error: 'no_token' };

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);

        try {
          const res = await fetch(WORKER_URL + '/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token }),
            signal: controller.signal,
          });
          clearTimeout(timeout);
          const data = await res.json();
          return data;
        } catch(e) {
          clearTimeout(timeout);
          if (e.name === 'AbortError') {
            return { ok: false, error: '请求超时，请检查网络后重试' };
          }
          return { ok: false, error: '网络错误，请检查网络后重试' };
        }
      },

  // ---------- 激活（调用 Worker /activate） ----------

  async activate(code) {
        let fpData;
        try {
          fpData = await collectFingerprint();
        } catch(e) {
          return { ok: false, error: '\u8bbe\u5907\u6307\u7eb9\u91c7\u96c6\u5931\u8d25\uff0c\u8bf7\u786e\u4fdd\u4f7f\u7528\u5b89\u5168\u8fde\u63a5(HTTPS)\u8bbf\u95ee' };
        }

        const timeout = setTimeout(() => {
          const btn = document.getElementById('auth-btn');
          if (btn) { btn.disabled = false; btn.textContent = '\u6fc0\u6d3b'; }
        }, 15000);

        try {
          const res = await fetch(WORKER_URL + '/activate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              code: code.toUpperCase(),
              fp: fpData.hash,
              canvas: fpData.canvas,
              stable: fpData.stable,
            }),
          });
          clearTimeout(timeout);
          const data = await res.json();

          if (data.ok && data.token) {
            try { localStorage.setItem(AUTH_KEY, data.token); } catch {}
            try {
              localStorage.setItem(FP_CACHE_KEY, JSON.stringify({
                hash: fpData.hash,
                canvas: fpData.canvas,
                stable: fpData.stable,
              }));
            } catch {}
          }

          return data;
        } catch(e) {
          clearTimeout(timeout);
          return { ok: false, error: '\u7f51\u7edc\u9519\u8bef\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u540e\u91cd\u8bd5' };
        }
      },

  // ---------- 清除认证 ----------

  logout() {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(FP_CACHE_KEY);
  },

  // ---------- 激活弹窗 ----------

  showActivationModal(onSuccess) {
    const overlay = document.getElementById('auth-overlay');
    if (overlay) {
      overlay.style.display = 'flex';
      const input = document.getElementById('auth-code');
      if (input) setTimeout(() => input.focus(), 200);
      return;
    }

    // 弹窗还不存在 → 创建
    this._createModal(onSuccess);
  },

  _createModal(onSuccess) {
    // 注入弹窗样式
    _injectAuthCSS();
    // 移除旧的（如果存在）
    const old = document.getElementById('auth-overlay');
    if (old) old.remove();

    const overlay = document.createElement('div');
    overlay.id = 'auth-overlay';
    overlay.className = 'auth-overlay';
    overlay.innerHTML =
      '<div class="auth-modal">' +
      '  <button class="auth-close" id="auth-close-btn" onclick="closeAuthModal()">×</button>' +
      '  <div class="auth-icon">🔑</div>' +
      '  <h2>访问码激活</h2>' +
      '  <p class="auth-desc">请输入您在知识星球获取的访问码，激活后即可查看全部报告</p>' +
      '  <input class="auth-input" id="auth-code" placeholder="输入访问码" maxlength="20" autocomplete="off" autocorrect="off" spellcheck="false">' +
      '  <button class="auth-btn" id="auth-btn">激活账号</button>' +
      '  <div class="auth-error" id="auth-error"></div>' +
      '  <div class="auth-recover">已购买？每个访问码可绑定 2 台设备，多设备输入同码即可</div>' +
      '  <div class="auth-footer">尚未加入？前往 <a href="https://t.zsxq.com/6iVvp" target="_blank" rel="noopener" style="color:#0071E3;text-decoration:none;font-weight:600">知识星球 · 蓝宝书Max</a> 订阅</div>' +
      '</div>';

    document.body.appendChild(overlay);

    // 事件绑定
    const input = document.getElementById('auth-code');
    const btn = document.getElementById('auth-btn');

    const doActivate = async () => {
      try {
        const code = input.value.trim();
        if (!code) { showError('请输入激活码'); return; }
        btn.disabled = true;
        btn.textContent = '验证中...';
        clearError();

        const safetyTimer = setTimeout(() => {
          btn.disabled = false;
          btn.textContent = '激活';
          showError('请求超时，请检查网络后重试');
        }, 10000);

        const result = await Paywall.activate(code);
        clearTimeout(safetyTimer);
        
        if (result.ok) {
          hideModal();
          const expiry = Paywall.formatExpiry();
          const expiryMsg = expiry ? '有效期至 ' + expiry : '';
          if (onSuccess) {
            if (expiryMsg) console.log('蓝宝书Max ' + expiryMsg);
            onSuccess();
          } else {
            if (expiryMsg) alert('激活成功！' + expiryMsg);
            window.location.reload();
          }
        } else {
          showError(result.error || '激活失败，请检查激活码');
          btn.disabled = false;
          btn.textContent = '激活';
          input.focus();
        }
      } catch(e) {
        console.error('激活异常:', e);
        showError('系统错误: ' + (e.message || '未知错误'));
        btn.disabled = false;
        btn.textContent = '激活';
      }
    };

    btn.addEventListener('click', doActivate);
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') doActivate();
    });
    input.addEventListener('input', () => clearError());
    setTimeout(() => input.focus(), 200);

    function showError(msg) {
      const el = document.getElementById('auth-error');
      if (el) el.textContent = msg;
    }
    function clearError() {
      const el = document.getElementById('auth-error');
      if (el) el.textContent = '';
    }
    function hideModal() {
      const o = document.getElementById('auth-overlay');
      if (o) o.style.display = 'none';
    }
    // Close button handler
    document.getElementById('auth-close-btn').addEventListener('click', hideModal);
  },
  closeAuthModal() {
    const o = document.getElementById('auth-overlay');
    if (o) o.style.display = 'none';
  },

  // ---------- 登录按钮回调（index.html 调用） ----------
  showLogin() {
    this.showActivationModal(null);
  },

  // ---------- 获取到期日 ----------
  getExpiryDate() {
    const expiresAt = localStorage.getItem(EXPIRES_KEY);
    if (!expiresAt) return null;
    const date = new Date(expiresAt);
    return isNaN(date.getTime()) ? null : date;
  },

  // ---------- 到期日格式化 ----------
  formatExpiry() {
    const date = this.getExpiryDate();
    if (!date) return '';
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return y + '/' + m + '/' + d;
  },

  // ---------- 报告页 lock icon 装饰 ----------
  lockIcon() {
    return '<span class="lock-icon">🔒</span>';
  },

  unlockBadge() {
    const expiry = this.formatExpiry();
    const text = expiry ? '✓ 已订阅 · 有效期至 ' + expiry : '✓ 已订阅';
    return '<span class="unlock-badge">' + text + '</span>';
  },
};

// ===== 全局关闭函数（供onclick调用） =====
function closeAuthModal() {
  Paywall.closeAuthModal();
}

// ===== 页面初始化检测（自动执行） =====

// 报告页 <html data-paywall="true"> 时启用付费墙
document.addEventListener('DOMContentLoaded', async () => {
  const needsAuth = document.documentElement.getAttribute('data-paywall') === 'true';
  if (!needsAuth) return;

  // 已认证 → 直接放行
  if (Paywall.isAuthenticated()) {
    document.documentElement.classList.add('bb-authenticated');
    return;
  }

  // 未认证 → 弹激活窗
  const title = document.title || '';
  Paywall.showActivationModal(() => {
    window.location.reload();
  });
});

// ===== 导航页认证状态更新（index.html 在事件中调用） =====
window.__bbmRefreshAuth = function() {
  const isAuth = Paywall.isAuthenticated();
  const badge = document.getElementById('auth-badge');
  if (badge) {
    badge.innerHTML = isAuth ? Paywall.unlockBadge() : '';
  }
  const btn = document.getElementById('btn-nav-login');
  if (btn) {
    btn.textContent = isAuth ? '已订阅' : '订阅';
    btn.style.background = isAuth
      ? 'rgba(52,199,89,.1)'
      : 'rgba(0,113,227,.08)';
    btn.style.color = isAuth ? '#34C759' : '#0071E3';
  }
};
