/**
 * 蓝宝书Max · 设备绑定鉴权系统
 * =============================
 *
 * 一人一号，绑定≤2台设备。
 * Token 自包含（纯计算验证，不读 KV）。
 * Canvas 指纹 + 容差匹配（兼容 iOS Safari）。
 * 清缓存恢复机制：同码+同IP+30天内自动识别。
 *
 * 手机端修复 (v5.1):
 *   - Canvas 采集加 3s 超时，超时自动降级到无Canvas模式
 *   - 激活总超时从 10s → 25s
 *   - Worker 验证超时从 10s → 15s
 */

// ===== 配置 =====
const WORKER_URL    = "https://bluebook-auth.bluebookmax.workers.dev";
const AUTH_KEY      = "bbm_auth_token";
const FP_CACHE_KEY  = "bbm_fp_cache";
const EXPIRES_KEY   = "bbm_expires_at";

// ===== 设备指纹采集 =====
async function collectFingerprint() {
  var nav = {
    ua: navigator.userAgent,
    platform: navigator.platform,
    lang: navigator.language,
    cores: navigator.hardwareConcurrency || 4,
    mem: navigator.deviceMemory || 0,
    pdf: navigator.pdfViewerEnabled || false,
    vendor: navigator.vendor || '',
  };
  var scr = {
    w: screen.width,
    h: screen.height,
    dpr: window.devicePixelRatio || 1,
    cd: screen.colorDepth || 24,
  };
  var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  // Canvas 指纹，带 3s 超时（iOS Safari 可能卡住）
  var canvasHash = await getCanvasWithTimeout(3000);

  var stableParts = [nav.ua, nav.platform, nav.lang, scr.w, scr.h, scr.dpr, tz].join('|||');
  var fp = await sha256(stableParts + '|||' + canvasHash);

  return { hash: fp, canvas: canvasHash, stable: stableParts };
}

// 带超时的 Canvas 采集
function getCanvasWithTimeout(ms) {
  return new Promise(function(resolve) {
    var done = false;
    var timer = setTimeout(function() {
      if (!done) { done = true; resolve('canvas-timeout'); }
    }, ms);
    try {
      var result = getCanvasHash();
      if (!done) { done = true; clearTimeout(timer); resolve(result); }
    } catch(e) {
      if (!done) { done = true; clearTimeout(timer); resolve('canvas-error'); }
    }
  });
}

function getCanvasHash() {
  try {
    var c = document.createElement('canvas');
    c.width = 200; c.height = 50;
    var ctx = c.getContext('2d');
    if (!ctx) return 'no-canvas';
    ctx.textBaseline = 'alphabetic';
    ctx.font = '16px "Arial",sans-serif';
    ctx.fillStyle = '#1D1D1F';
    ctx.fillText('蓝宝书Max', 10, 30);
    ctx.fillStyle = '#0071E3';
    ctx.fillRect(10, 10, 40, 20);
    var data = c.toDataURL();
    if (data.length < 100) return 'canvas-blocked';
    return data.substring(50, 250);
  } catch(e) {
    return 'canvas-error';
  }
}

// SHA-256 hash (with fallback for non-HTTPS)
async function sha256(str) {
  if (!crypto || !crypto.subtle || !crypto.subtle.digest) {
    var h = 0;
    for (var i = 0; i < str.length; i++) { h = ((h << 5) - h) + str.charCodeAt(i); h |= 0; }
    return 'fp_' + Math.abs(h).toString(16);
  }
  try {
    var buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
    return Array.from(new Uint8Array(buf)).map(function(b) { return b.toString(16).padStart(2, '0'); }).join('');
  } catch(e) {
    var h = 0;
    for (var i = 0; i < str.length; i++) { h = ((h << 5) - h) + str.charCodeAt(i); h |= 0; }
    return 'fp_' + Math.abs(h).toString(16);
  }
}

// ===== Paywall 对象 =====
var Paywall = {

  isAuthenticated: function() {
    var t = localStorage.getItem(AUTH_KEY);
    if (!t) return false;
    var parts = t.split('.');
    return parts.length === 3 && parts[1].length > 0;
  },

  getToken: function() {
    return localStorage.getItem(AUTH_KEY);
  },

  getTokenExpiry: function() {
    try {
      var t = this.getToken();
      if (!t) return 0;
      var expires = parseInt(t.split('.')[2], 10);
      return isNaN(expires) ? 0 : expires;
    } catch(e) { return 0; }
  },

  isTokenExpired: function() {
    return Date.now() > this.getTokenExpiry();
  },

  verifyWithWorker: async function() {
    var token = this.getToken();
    if (!token) return { ok: false, error: 'no_token' };

    var controller = new AbortController();
    var timeout = setTimeout(function() { controller.abort(); }, 15000);

    try {
      var res = await fetch(WORKER_URL + '/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      return await res.json();
    } catch(e) {
      clearTimeout(timeout);
      if (e.name === 'AbortError') {
        return { ok: false, error: '请求超时，请检查网络后重试' };
      }
      return { ok: false, error: '网络错误，请检查网络后重试' };
    }
  },

  activate: async function(code) {
    var fpData;
    try {
      fpData = await collectFingerprint();
    } catch(e) {
      return { ok: false, error: '设备指纹采集失败，请确保使用安全连接(HTTPS)访问' };
    }

    var timeout = setTimeout(function() {
      var btn = document.getElementById('auth-btn');
      if (btn) { btn.disabled = false; btn.textContent = '激活'; }
    }, 25000);

    try {
      var res = await fetch(WORKER_URL + '/activate', {
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
      var data = await res.json();

      if (data.ok && data.token) {
        try { localStorage.setItem(AUTH_KEY, data.token); } catch(e) {}
        try {
          localStorage.setItem(FP_CACHE_KEY, JSON.stringify({
            hash: fpData.hash, canvas: fpData.canvas, stable: fpData.stable,
          }));
        } catch(e) {}
      }

      return data;
    } catch(e) {
      clearTimeout(timeout);
      return { ok: false, error: '网络错误，请检查网络后重试' };
    }
  },

  logout: function() {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(FP_CACHE_KEY);
  },

  showActivationModal: function(onSuccess) {
    var overlay = document.getElementById('auth-overlay');
    if (overlay) {
      overlay.style.display = 'flex';
      var input = document.getElementById('auth-code');
      if (input) setTimeout(function() { input.focus(); }, 200);
      return;
    }
    this._createModal(onSuccess);
  },

  _createModal: function(onSuccess) {
    var old = document.getElementById('auth-overlay');
    if (old) old.remove();

    var overlay = document.createElement('div');
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

    var input = document.getElementById('auth-code');
    var btn = document.getElementById('auth-btn');

    var doActivate = async function() {
      try {
        var code = input.value.trim();
        if (!code) { showError('请输入激活码'); return; }
        btn.disabled = true;
        btn.textContent = '验证中...';
        clearError();

        var safetyTimer = setTimeout(function() {
          btn.disabled = false;
          btn.textContent = '激活';
          showError('请求超时，请检查网络后重试');
        }, 25000);

        var result = await Paywall.activate(code);
        clearTimeout(safetyTimer);

        if (result.ok) {
          hideModal();
          var expiry = Paywall.formatExpiry();
          var expiryMsg = expiry ? '有效期至 ' + expiry : '';
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
    input.addEventListener('keydown', function(e) { if (e.key === 'Enter') doActivate(); });
    input.addEventListener('input', function() { clearError(); });
    setTimeout(function() { input.focus(); }, 200);

    function showError(msg) {
      var el = document.getElementById('auth-error');
      if (el) el.textContent = msg;
    }
    function clearError() {
      var el = document.getElementById('auth-error');
      if (el) el.textContent = '';
    }
    function hideModal() {
      var o = document.getElementById('auth-overlay');
      if (o) o.style.display = 'none';
    }
    document.getElementById('auth-close-btn').addEventListener('click', hideModal);
  },

  closeAuthModal: function() {
    var o = document.getElementById('auth-overlay');
    if (o) o.style.display = 'none';
  },

  showLogin: function() {
    this.showActivationModal(null);
  },

  getExpiryDate: function() {
    var expiresAt = localStorage.getItem(EXPIRES_KEY);
    if (!expiresAt) return null;
    var date = new Date(expiresAt);
    return isNaN(date.getTime()) ? null : date;
  },

  formatExpiry: function() {
    var date = this.getExpiryDate();
    if (!date) return '';
    var y = date.getFullYear();
    var m = String(date.getMonth() + 1).padStart(2, '0');
    var d = String(date.getDate()).padStart(2, '0');
    return y + '/' + m + '/' + d;
  },

  lockIcon: function() {
    return '<span class="lock-icon">🔒</span>';
  },

  unlockBadge: function() {
    var expiry = this.formatExpiry();
    var text = expiry ? '✓ 已订阅 · 有效期至 ' + expiry : '✓ 已订阅';
    return '<span class="unlock-badge">' + text + '</span>';
  },
};

function closeAuthModal() {
  Paywall.closeAuthModal();
}

document.addEventListener('DOMContentLoaded', async function() {
  var needsAuth = document.documentElement.getAttribute('data-paywall') === 'true';
  if (!needsAuth) return;

  if (Paywall.isAuthenticated()) {
    document.documentElement.classList.add('bb-authenticated');
    return;
  }

  Paywall.showActivationModal(function() {
    window.location.reload();
  });
});

window.__bbmRefreshAuth = function() {
  var isAuth = Paywall.isAuthenticated();
  var badge = document.getElementById('auth-badge');
  if (badge) {
    badge.innerHTML = isAuth ? Paywall.unlockBadge() : '';
  }
  var btn = document.getElementById('btn-nav-login');
  if (btn) {
    btn.textContent = isAuth ? '已订阅' : '订阅';
    btn.style.background = isAuth ? 'rgba(52,199,89,.1)' : 'rgba(0,113,227,.08)';
    btn.style.color = isAuth ? '#34C759' : '#0071E3';
  }
};
