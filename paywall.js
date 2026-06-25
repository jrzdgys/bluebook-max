/** 蓝宝书Max · 设备绑定鉴权系统 v5（单通道-Worker） */
    var WORKER_URL = 'https://bluebook-auth.bluebookmax.workers.dev';
    var AUTH_KEY = 'bbm_auth_token';
    var FP_CACHE_KEY = 'bbm_fp_cache';
    var EXPIRES_KEY = 'bbm_expires_at';

    function collectFingerprint() {
      try {
      console.log('[BBM] Collecting fingerprint...');
      } catch(e){}
      return new Promise(function(resolve) {
        var nav = {
          ua: navigator.userAgent, platform: navigator.platform, lang: navigator.language,
          cores: navigator.hardwareConcurrency || 4, vendor: navigator.vendor || '',
        };
        var scr = { w: screen.width, h: screen.height, dpr: window.devicePixelRatio || 1, cd: screen.colorDepth || 24 };
        var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        getCanvasHash().then(function(canvasHash) {
          var stableParts = [nav.ua, nav.platform, nav.lang, scr.w, scr.h, scr.dpr, tz].join('|||');
          sha256(stableParts + '|||' + canvasHash).then(function(fp) {
            resolve({ hash: fp, canvas: canvasHash, stable: stableParts, ua: nav.ua });
          }).catch(function() {
            var h = 0; var s = stableParts + '|||' + canvasHash;
            for (var i = 0; i < s.length; i++) { h = ((h << 5) - h) + s.charCodeAt(i); h |= 0; }
            resolve({ hash: 'fp_' + Math.abs(h).toString(16), canvas: canvasHash, stable: stableParts, ua: nav.ua });
          });
        });
      });
    }

    function getCanvasHash() {
      return new Promise(function(resolve) {
        if (/iPhone|iPad|iPod/i.test(navigator.userAgent)) {
          var iosStable = (screen.width+'x'+screen.height+'|'+Intl.DateTimeFormat().resolvedOptions().timeZone+'|'+navigator.language);
          var iosHash = 0; for(var i=0;i<iosStable.length;i++){iosHash=((iosHash<<5)-iosHash)+iosStable.charCodeAt(i);iosHash|=0;}
          resolve('ios-' + Math.abs(iosHash).toString(16));
          return;
        }
        var timer = setTimeout(function() { resolve('canvas-timeout-' + Date.now()); }, 3000);
        try {
          var c = document.createElement('canvas'); c.width = 200; c.height = 50;
          var ctx = c.getContext('2d');
          if (!ctx) { clearTimeout(timer); resolve('no-ctx-' + Date.now()); return; }
          ctx.textBaseline = 'alphabetic'; ctx.font = '14px Arial,sans-serif';
          ctx.fillStyle = '#1D1D1F'; ctx.fillText('BluebookMax', 10, 30);
          ctx.fillStyle = '#0071E3'; ctx.fillRect(10, 10, 40, 20);
          try { var data = c.toDataURL(); clearTimeout(timer);
            resolve(data ? data.substring(50, 250) : 'empty-' + Date.now());
          } catch(e) { clearTimeout(timer); resolve('canvas-error-' + Date.now()); }
        } catch(e) { clearTimeout(timer); resolve('canvas-exception-' + Date.now()); }
      });
    }

    function sha256(str) {
      return new Promise(function(resolve) {
        if (!crypto || !crypto.subtle || !crypto.subtle.digest) {
          var h = 0; for (var i = 0; i < str.length; i++) { h = ((h << 5) - h) + str.charCodeAt(i); h |= 0; }
          resolve('fp_' + Math.abs(h).toString(16)); return;
        }
        try {
          crypto.subtle.digest('SHA-256', new TextEncoder().encode(str)).then(function(buf) {
            resolve(Array.from(new Uint8Array(buf)).map(function(b) { return b.toString(16).padStart(2, '0'); }).join(''));
          }).catch(function() {
            var h = 0; for (var i = 0; i < str.length; i++) { h = ((h << 5) - h) + str.charCodeAt(i); h |= 0; }
            resolve('fp_' + Math.abs(h).toString(16));
          });
        } catch(e) {
          var h = 0; for (var i = 0; i < str.length; i++) { h = ((h << 5) - h) + str.charCodeAt(i); h |= 0; }
          resolve('fp_' + Math.abs(h).toString(16));
        }
      });
    }

    function _storeToken(token, fpData) {
      try {
        localStorage.setItem(AUTH_KEY, token);
        localStorage.setItem(FP_CACHE_KEY, JSON.stringify({ hash: fpData.hash, canvas: fpData.canvas, stable: fpData.stable }));
        var exp = parseInt(token.split('.')[2], 10);
        if (!isNaN(exp)) localStorage.setItem(EXPIRES_KEY, String(exp));
      } catch(e) {}
    }

    function _injectAuthCSS() {
      if (document.getElementById('bbm-auth-styles')) return;
      var s = document.createElement('style'); s.id = 'bbm-auth-styles';
      s.textContent = '.auth-overlay{position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.5);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;animation:pwFade .3s ease}' +
        '.auth-modal{background:rgba(255,255,255,.95);backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);border-radius:20px;padding:40px 32px;max-width:380px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.2);text-align:center;position:relative}' +
        '.auth-icon{font-size:48px;margin-bottom:12px}.auth-modal h2{font-size:22px;font-weight:700;margin-bottom:6px}.auth-desc{font-size:14px;color:#86868B;margin-bottom:24px}' +
        '.auth-input{width:100%;height:48px;border:1.5px solid #D2D2D7;border-radius:12px;padding:0 16px;font-size:16px;text-align:center;letter-spacing:2px;outline:none;transition:border-color .2s,box-shadow .2s;box-sizing:border-box}' +
        '.auth-input:focus{border-color:#0071E3;box-shadow:0 0 0 4px rgba(0,113,227,.12)}' +
        '.auth-btn{width:100%;height:48px;border:none;border-radius:12px;font-size:16px;font-weight:600;cursor:pointer;background:#0071E3;color:#fff;margin-top:14px;transition:opacity .2s}' +
        '.auth-btn:hover{opacity:.85}.auth-btn:disabled{opacity:.4;cursor:not-allowed}' +
        '.auth-error{color:#FF3B30;font-size:13px;margin-top:10px;min-height:20px}' +
        '.auth-close{position:absolute;top:12px;right:14px;background:none;border:none;font-size:22px;color:#AEAEB2;cursor:pointer;padding:4px 12px;border-radius:8px;line-height:1;transition:all .15s;font-family:inherit}' +
        '.auth-close:hover{background:rgba(0,0,0,.05);color:#1D1D1F}.auth-recover{font-size:12px;color:#AEAEB2;margin-top:8px;font-style:italic}.auth-footer{font-size:13px;color:#86868B;margin-top:20px;padding-top:16px;border-top:1px solid #E5E5EA}' +
        '@keyframes pwFade{from{opacity:0}to{opacity:1}}';
      document.head.appendChild(s);
    }

    function buildModalHTML() {
      var div = document.createElement('div');
      div.className = 'auth-modal';
      var html = '';
      html += '<button class="auth-close" id="auth-close-btn">&times;</button>';
      html += '<div class="auth-icon">&#x1F511;</div>';
      html += '<h2>' + '访问码激活' + '</h2>';
      html += '<p class="auth-desc">请输入您在知识星球获取的访问码</p>';
      html += '<input class="auth-input" id="auth-code" placeholder="输入访问码" maxlength="20" autocomplete="off" autocorrect="off" spellcheck="false">';
      html += '<button class="auth-btn" id="auth-btn">激活账号</button>';
      html += '<div class="auth-error" id="auth-error"></div>';
      html += '<div class="auth-recover">每个访问码可绑定多台设备</div>';
      html += '<div class="auth-footer">尚未加入？前往 <a href="https://t.zsxq.com/6iVvp" target="_blank" style="color:#0071E3;text-decoration:none;font-weight:600">知识星球 · 蓝宝书Max</a></div>';
      div.innerHTML = html;
      return div;
    }

    
    // 本地降级验证：当Worker不可用时使用
    function _localVerify(code) {
      var codeStr = code.toUpperCase().trim();
      var encoder = new TextEncoder();
      var data = encoder.encode(codeStr);
      return crypto.subtle.digest('SHA-256', data).then(function(buf) {
        var hash = Array.from(new Uint8Array(buf)).map(function(b) { return b.toString(16).padStart(2,'0'); }).join('');
        var match = (typeof VALID_HASHES !== 'undefined' && VALID_HASHES.indexOf(hash) >= 0);
        if (match) {
          var expiry = Date.now() + 86400000 * 365; // 1 year fallback expiry
          var token = 'local_' + btoa(codeStr) + '.' + hash + '.' + expiry;
          _storeToken(token, {hash: hash, canvas: '', stable: '', ua: navigator.userAgent});
          return { ok: true, reason: 'local_fallback', token: token, message: '验证通过（本地模式）' };
        }
        return { ok: false, error: '访问码无效' };
      }).catch(function() {
        return { ok: false, error: '验证失败' };
      });
    }
    
    var Paywall = {
      isAuthenticated: function() {
        var t = localStorage.getItem(AUTH_KEY);
        if (!t) return false;
        var parts = t.split('.');
        if (parts.length < 3) return false;
        var expires = parseInt(parts[2], 10);
        if (isNaN(expires)) return false;
        if (expires < Date.now() - 86400000 * 30) return false;
        if (expires < Date.now()) return false;
        return true;
      },
      getToken: function() { return localStorage.getItem(AUTH_KEY); },
      activate: function(code) {
        return collectFingerprint().then(function(fpData) {
          var controller = new AbortController();
          var timeout = setTimeout(function() { controller.abort(); }, 30000);
          return fetch(WORKER_URL + '/activate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code.toUpperCase(), fp: fpData.hash, canvas: fpData.canvas, stable: fpData.stable, ua: fpData.ua }),
            signal: controller.signal,
          }).then(function(res) {
            clearTimeout(timeout);
            return res.json();
          }).then(function(data) {
            if (data.ok && data.token) {
              console.log('[BBM] Activation successful, storing token');
              _storeToken(data.token, fpData);
            }
            return data;
          }).catch(function(e) {
            clearTimeout(timeout);
            console.error('[BBM] Fetch error:', e.name, e.message);
            return { ok: false, error: '网络请求失败，请检查网络连接（如使用移动数据可尝试切换WiFi），若持续失败请联系管理员' };
          });
        }).catch(function(e) {
          console.error('[BBM] Fingerprint error:', e);
          return { ok: false, error: '设备指纹采集失败' };
        });
      },
      logout: function() { localStorage.removeItem(AUTH_KEY); localStorage.removeItem(FP_CACHE_KEY); localStorage.removeItem(EXPIRES_KEY); },
      showActivationModal: function(onSuccess) {
        var overlay = document.getElementById('auth-overlay');
        if (overlay) { overlay.style.display = 'flex'; var inp = document.getElementById('auth-code'); if (inp) setTimeout(function() { inp.focus(); }, 200); return; }
        this._createModal(onSuccess);
      },
      _createModal: function(onSuccess) {
        _injectAuthCSS();
        var old = document.getElementById('auth-overlay'); if (old) old.remove();
        var overlay = document.createElement('div'); overlay.id = 'auth-overlay'; overlay.className = 'auth-overlay';
        var modalDiv = buildModalHTML();
        overlay.appendChild(modalDiv);
        document.body.appendChild(overlay);
        var input = document.getElementById('auth-code');
        var btn = document.getElementById('auth-btn');
        var doActivate = function() {
          var code = input.value.trim(); if (!code) { showError('请输入激活码'); return; }
          console.log('[BBM] Activating code:', code);
          btn.disabled = true; btn.textContent = '验证中...'; clearError();
          var safetyTimer = setTimeout(function() {
            btn.disabled = false; btn.textContent = '重新验证';
            showError('请求超时，请检查网络后重试');
          }, 35000);
          Paywall.activate(code).then(function(result) {
            clearTimeout(safetyTimer);
            if (result.ok) { hideModal(); if (onSuccess) onSuccess(); else window.location.reload(); }
            else { showError(result.error || '激活失败，请检查激活码'); btn.disabled = false; btn.textContent = '激活账号'; if (input) input.focus(); }
          }).catch(function() { clearTimeout(safetyTimer); showError('系统错误，请稍后重试'); btn.disabled = false; btn.textContent = '激活账号'; });
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
      closeAuthModal: function() { var o = document.getElementById('auth-overlay'); if (o) o.style.display = 'none'; },
      showLogin: function() { this.showActivationModal(null); },
      getExpiryDate: function() {
        var expiresAt = localStorage.getItem(EXPIRES_KEY); if (!expiresAt) return null;
        var date = new Date(parseInt(expiresAt, 10)); return isNaN(date.getTime()) ? null : date;
      },
      formatExpiry: function() {
        var date = Paywall.getExpiryDate(); if (!date) return '';
        return date.getFullYear() + '/' + String(date.getMonth()+1).padStart(2,'0') + '/' + String(date.getDate()).padStart(2,'0');
      },
      unlockBadge: function() {
        var expiry = Paywall.formatExpiry();
        var text = expiry ? '已订阅 · 有效期至 ' + expiry : '已订阅';
        return '<span class="unlock-badge">' + text + '</span>';
      },
    };

    document.addEventListener('DOMContentLoaded', function() {
      var needsAuth = document.documentElement.getAttribute('data-paywall') === 'true';
      if (!needsAuth) return;
      if (Paywall.isAuthenticated()) {
        document.documentElement.classList.add('bb-authenticated');
        var expiresAt = localStorage.getItem(EXPIRES_KEY);
        if (expiresAt) {
          var daysLeft = Math.ceil((parseInt(expiresAt, 10) - Date.now()) / 86400000);
          if (daysLeft >= 0 && daysLeft <= 7) {
            var banner = document.createElement('div');
            banner.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:9999;padding:12px 20px;text-align:center;font-size:14px;font-weight:500;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);transition:opacity .5s;cursor:pointer';
            if (daysLeft <= 1) {
              banner.style.background = 'rgba(255,59,48,.92)';
              banner.style.color = '#fff';
              banner.textContent = daysLeft === 0 ? '⚠️ 订阅将于今天到期，请及时续费' : '⚠️ 订阅将于明天到期，请及时续费';
            } else {
              banner.style.background = 'rgba(255,149,0,.92)';
              banner.style.color = '#fff';
              banner.textContent = '⚠️ 订阅将于 ' + daysLeft + ' 天后到期，续费请访问知识星球 →';
            }
            banner.onclick = function() { banner.style.opacity = '0'; setTimeout(function(){if(banner.parentNode)banner.parentNode.removeChild(banner);},500); };
            document.body.appendChild(banner);
            setTimeout(function() { banner.style.opacity = '0'; setTimeout(function(){if(banner.parentNode)banner.parentNode.removeChild(banner);},500); }, 8000);
          }
        }
        return;
      }
      Paywall.showActivationModal(function() { window.location.reload(); });
    });

    window.__bbmRefreshAuth = function() {
      var isAuth = Paywall.isAuthenticated();
      var badge = document.getElementById('auth-badge');
      if (badge) badge.innerHTML = isAuth ? Paywall.unlockBadge() : '';
      var btn = document.getElementById('btn-nav-login');
      if (btn) { btn.textContent = isAuth ? '已订阅' : '订阅'; btn.style.background = isAuth ? 'rgba(52,199,89,.1)' : 'rgba(0,113,227,.08)'; btn.style.color = isAuth ? '#34C759' : '#0071E3'; }
    };
    