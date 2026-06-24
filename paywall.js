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
  try {
    const c = document.createElement('canvas');
    c.width = 200; c.height = 50;
    const ctx = c.getContext('2d');
    if (!ctx) return 'no-canvas';

    // 写固定文字
    ctx.textBaseline = 'alphabetic';
    ctx.font = '16px "Arial",sans-serif';
    ctx.fillStyle = '#1D1D1F';
    ctx.fillText('蓝宝书Max', 10, 30);
    ctx.fillStyle = '#0071E3';
    ctx.fillRect(10, 10, 40, 20);

    // iOS Safari 隐私模式可能返回空，捕获这种情况
    const data = c.toDataURL();
    if (data.length < 100) return 'canvas-blocked';
    return data.substring(50, 250); // 取中间段作为指纹

  } catch(e) {
    return 'canvas-error';
  }
}

// SHA-256 hash
async function sha256(str) {
  const buf = await crypto.subtle.digest('SHA-256',
    new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, '0')).join('');
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

    try {
      const res = await fetch(WORKER_URL + '/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      const data = await res.json();
      return data;
    } catch(e) {
      // Worker 不可达时，本地 token 未过期则放行
      if (!this.isTokenExpired()) {
        return { ok: true, offline: true };
      }
      return { ok: false, error: 'worker_unreachable' };
    }
  },

  // ---------- 激活（调用 Worker /activate） ----------

  async activate(code) {
    const fpData = await collectFingerprint();

    try {
      const res = await fetch(WORKER_URL + '/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: code.toUpperCase(),
          fp: fpData.hash,
        }),
      });
      const data = await res.json();

      if (data.ok && data.token) {
        localStorage.setItem(AUTH_KEY, data.token);
        // 缓存指纹用于恢复
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
      return { ok: false, error: '网络错误，请检查网络后重试' };
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
    // 移除旧的（如果存在）
    const old = document.getElementById('auth-overlay');
    if (old) old.remove();

    const overlay = document.createElement('div');
    overlay.id = 'auth-overlay';
    overlay.className = 'auth-overlay';
    overlay.innerHTML =
      '<div class="auth-modal">' +
      '  <button class="auth-close" id="auth-close-btn" onclick="closeAuthModal()">×</button>' +
      '  <div class="auth-icon">📘</div>' +
      '  <h2>蓝宝书Max</h2>' +
      '  <p class="auth-desc">请输入您的访问码激活账号</p>' +
      '  <input class="auth-input" id="auth-code" placeholder="BBM-XXXXXXXX" maxlength="14" autocomplete="off" autocorrect="off" spellcheck="false">' +
      '  <button class="auth-btn" id="auth-btn">激活</button>' +
      '  <div class="auth-error" id="auth-error"></div>' +
      '  <div class="auth-recover">已有账号？输入激活码后系统会自动识别设备，重新激活。</div>' +
      '  <div class="auth-footer">激活即表示同意服务条款 · 每账号限绑定 2 台设备</div>' +
      '</div>';

    document.body.appendChild(overlay);

    // 事件绑定
    const input = document.getElementById('auth-code');
    const btn = document.getElementById('auth-btn');

    const doActivate = async () => {
      const code = input.value.trim();
      if (!code) { showError('请输入激活码'); return; }
      btn.disabled = true;
      btn.textContent = '验证中...';
      clearError();

      const result = await Paywall.activate(code);
      if (result.ok) {
        hideModal();
        if (onSuccess) onSuccess();
        else window.location.reload();
      } else {
        showError(result.error || '激活失败，请检查激活码');
        btn.disabled = false;
        btn.textContent = '激活';
        input.focus();
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

  // ---------- 报告页 lock icon 装饰 ----------
  lockIcon() {
    return '<span class="lock-icon">🔒</span>';
  },

  unlockBadge() {
    return '<span class="unlock-badge">✓ 已订阅</span>';
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
