/**
 * 蓝宝书Max · 付费墙鉴权系统 v4
 * ==============================
 *
 * 规则：
 *   索引页（index.html）→ 完全开放，不弹付费墙
 *   报告页（reports/*.html）→ 免费试看 1 份（按文件路径记录，不按日期重置）
 *                           → 第2份起弹出付费墙，需输入访问码
 *                           → 付费墙有关闭按钮，可关闭（但不看内容）
 *
 * 星球：蓝宝书Max · https://t.zsxq.com/6iVvp
 */

const ZSXQ_URL = "https://t.zsxq.com/6iVvp";
const ZSXQ_NAME = "蓝宝书Max";

const AUTH_KEY  = "bbmax_auth_v4";
const FREE_KEY  = "bbmax_free_v4";       // 免费试看过的报告文件路径（JSON数组）

const Paywall = {

  // ===== 认证 =====
  isAuthenticated() {
    try {
      const a = JSON.parse(localStorage.getItem(AUTH_KEY) || "{}");
      return a.valid === true;
    } catch { return false; }
  },

  getAuthInfo() {
    try { return JSON.parse(localStorage.getItem(AUTH_KEY) || "{}"); }
    catch { return {}; }
  },

  // ===== 免费试看（按文件路径记录，仅1份） =====
  _getFreeList() {
    try { return JSON.parse(localStorage.getItem(FREE_KEY) || "[]"); }
    catch { return []; }
  },

  _saveFreeList(list) {
    localStorage.setItem(FREE_KEY, JSON.stringify(list));
  },

  /** 当前页面还可以免费看吗？ */
  hasFreeView() {
    if (this.isAuthenticated()) return false; // 已付费无需免费
    const list = this._getFreeList();
    // 只有列表为空（从未看过任何免费报告）才能再看
    return list.length === 0;
  },

  /** 标记当前页面已免费看过（页面加载成功后调用） */
  useFreeView() {
    const path = this._currentReportPath();
    const list = this._getFreeList();
    if (!list.includes(path)) {
      list.push(path);
      this._saveFreeList(list);
    }
  },

  /** 当前报告在网站内的相对路径 */
  _currentReportPath() {
    try {
      const u = new URL(window.location.href);
      return u.pathname.replace(/\/$/, "") || "/";
    } catch { return "/"; }
  },

  // ===== SHA-256 =====
  async sha256(message) {
    const enc = new TextEncoder();
    const buf = await crypto.subtle.digest("SHA-256", enc.encode(message));
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
  },

  // ===== 验证访问码 =====
  async verify(code) {
    if (!code || code.trim().length < 4) {
      return { success: false, message: "访问码格式不正确" };
    }
    const hash = await this.sha256(code.trim());
    if (typeof VALID_HASHES !== "undefined" && VALID_HASHES.includes(hash)) {
      const idx = VALID_HASHES.indexOf(hash);
      localStorage.setItem(AUTH_KEY, JSON.stringify({
        valid: true,
        codeId: idx,
        activatedAt: Date.now(),
        codePrefix: code.trim().substring(0, 2),
      }));
      return { success: true, message: "验证成功！欢迎加入蓝宝书Max" };
    }
    return { success: false, message: "访问码无效，请在知识星球「" + ZSXQ_NAME + "」获取最新码" };
  },

  logout() {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(FREE_KEY);
  },

  // ===== 付费墙 UI（可关闭） =====
  renderPaywall(containerId, reportTitle) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const title = reportTitle || document.title || "";

    container.innerHTML = `
    <div class="pw-overlay" id="pw-overlay"
         style="position:fixed;top:0;left:0;width:100%;height:100%;
                background:rgba(0,0,0,.6);backdrop-filter:blur(16px);
                -webkit-backdrop-filter:blur(16px);z-index:10000;
                display:flex;align-items:center;justify-content:center;
                animation:pwFade .3s ease">
      <style>
        @keyframes pwFade{from{opacity:0}to{opacity:1}}
        @keyframes pwSlide{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
        .pw-card2{
          background:#fff;border-radius:20px;padding:40px 32px;
          max-width:420px;width:92%;text-align:center;
          box-shadow:0 20px 60px rgba(0,0,0,.18);
          animation:pwSlide .4s cubic-bezier(.16,1,.3,1);
          position:relative;margin:auto;
        }
        .pw-close2{
          position:absolute;top:10px;right:14px;
          width:32px;height:32px;border:none;background:#F2F2F7;
          border-radius:50%;font-size:16px;color:#86868B;
          cursor:pointer;display:flex;align-items:center;justify-content:center;
          transition:all .15s;line-height:1;
        }
        .pw-close2:hover{background:#E5E5EA;color:#1D1D1F}
        .pw-icon2{font-size:44px;margin-bottom:12px}
        .pw-card2 h2{font-size:20px;font-weight:700;color:#1D1D1F;margin-bottom:8px}
        .pw-desc2{font-size:13px;color:#86868B;line-height:1.6;margin-bottom:24px}
        .pw-input2{
          width:100%;padding:12px 16px;border:1.5px solid #E5E5EA;border-radius:12px;
          font-size:15px;font-family:inherit;text-align:center;letter-spacing:1px;
          outline:none;transition:border-color .15s;margin-bottom:10px;
          -webkit-appearance:none;-moz-appearance:none;appearance:none;
        }
        .pw-input2:focus{border-color:#0071E3}
        .pw-btn2{
          width:100%;padding:12px;background:#0071E3;color:#fff;border:none;
          border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;
          font-family:inherit;transition:all .15s;
        }
        .pw-btn2:hover{background:#0077ED}
        .pw-btn2:disabled{opacity:.6;cursor:not-allowed}
        .pw-err2{color:#FF3B30;font-size:12px;margin-top:8px;min-height:20px}
        .pw-ft2{
          margin-top:24px;padding-top:20px;border-top:1px solid #F2F2F7;
          font-size:12px;color:#AEAEB2;
        }
        .pw-ft2 a{
          display:inline-flex;align-items:center;gap:6px;margin-top:10px;
          padding:10px 24px;background:linear-gradient(135deg,#1AAD19,#0F8F0F);
          color:#fff;border-radius:12px;text-decoration:none;
          font-size:13px;font-weight:600;transition:all .15s;
        }
        .pw-ft2 a:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(26,173,25,.3)}
      </style>
      <div class="pw-card2">
        <button class="pw-close2" id="pw-close2" title="关闭">✕</button>
        <div class="pw-icon2">🔐</div>
        <h2>知识星球付费会员专享</h2>
        <p class="pw-desc2">
          ${title}<br>
          蓝宝书Max 为付费订阅产品<br>
          年费 ¥888，加入「${ZSXQ_NAME}」获取访问码
        </p>

        <input class="pw-input2" type="text" id="pw-code-input2"
               placeholder="输入访问码" autocomplete="off" maxlength="64">
        <button class="pw-btn2" id="pw-submit-btn2">验证访问码</button>
        <div class="pw-err2" id="pw-error2"></div>

        <div class="pw-ft2">
          <p style="margin-bottom:8px">没有访问码？加入知识星球获取</p>
          <a href="${ZSXQ_URL}" target="_blank" rel="noopener">🪐 加入蓝宝书Max · 年费 ¥888</a>
        </div>
      </div>
    </div>`;

    const overlay = document.getElementById("pw-overlay");
    const closeBtn = document.getElementById("pw-close2");
    const input = document.getElementById("pw-code-input2");
    const btn = document.getElementById("pw-submit-btn2");
    const err = document.getElementById("pw-error2");

    // 关闭按钮：关闭付费墙，显示"只有付费会员可查看"提示
    closeBtn.addEventListener("click", () => {
      if (overlay) overlay.remove();
      // 显示一个友好的空状态
      const c = document.querySelector(".container") || document.body;
      const msg = document.createElement("div");
      msg.id = "pw-blocked-msg";
      msg.style.cssText = "text-align:center;padding:80px 20px;color:#86868B";
      msg.innerHTML = `
        <div style="font-size:48px;margin-bottom:20px">🔐</div>
        <h2 style="font-size:20px;color:#1D1D1F;margin-bottom:8px">付费会员专享内容</h2>
        <p style="font-size:14px;margin-bottom:24px">蓝宝书Max 为知识星球付费产品，年费 ¥888</p>
        <a href="${ZSXQ_URL}" target="_blank" rel="noopener"
           style="display:inline-flex;align-items:center;gap:6px;padding:12px 28px;
                  background:linear-gradient(135deg,#1AAD19,#0F8F0F);color:#fff;
                  border-radius:12px;text-decoration:none;font-size:14px;font-weight:600">
          🪐 加入${ZSXQ_NAME} · ¥888/年
        </a>
        <p style="margin-top:18px;font-size:12px;color:#AEAEB2">
          已付费？<a href="javascript:location.reload()" style="color:#0071E3;cursor:pointer">刷新页面</a> 重新验证
        </p>`;
      if (c) c.innerHTML = "";
      if (c) c.appendChild(msg);
    });

    // 验证按钮
    const doVerify = async () => {
      btn.disabled = true;
      btn.textContent = "验证中...";
      err.textContent = "";
      const result = await Paywall.verify(input.value);
      if (result.success) {
        window.location.reload();
      } else {
        err.textContent = result.message;
        btn.disabled = false;
        btn.textContent = "验证访问码";
        input.focus(); input.select();
      }
    };
    btn.addEventListener("click", doVerify);
    input.addEventListener("keydown", e => { if (e.key === "Enter") doVerify(); });
    setTimeout(() => input.focus(), 300);
  },

  // ===== 装饰 =====
  lockIcon() { return '<span style="font-size:14px;margin-left:4px;opacity:.5">🔒</span>'; },
  unlockBadge() {
    return '<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;background:#EEFFF2;color:#34C759;border-radius:100px;font-size:11px;font-weight:600">✓ 已订阅</span>';
  },
};

// ===== 页面自动检测（仅报告页） =====
document.addEventListener("DOMContentLoaded", () => {
  const needsAuth = document.documentElement.getAttribute("data-paywall") === "true";
  if (!needsAuth) return;

  // 确保 codes.js 已加载
  if (typeof VALID_HASHES === "undefined") {
    console.warn("[蓝宝书Max] codes.js 未加载，无法验证访问码");
    return;
  }

  // 已认证 → 直接放行
  if (Paywall.isAuthenticated()) {
    document.documentElement.classList.add("bb-authenticated");
    return;
  }

  // 有免费试看次数 → 放行，页面加载完毕后再标记
  if (Paywall.hasFreeView()) {
    document.documentElement.classList.add("bb-free-view");

    // 显示底部免费试看提示条
    const banner = document.createElement("div");
    banner.style.cssText =
      "position:fixed;bottom:0;left:0;right:0;z-index:9999;" +
      "background:linear-gradient(135deg,#FFF9F0,#FFF0E0);" +
      "color:#C47A00;text-align:center;padding:8px 16px;" +
      "font-size:12px;font-weight:600;" +
      "box-shadow:0 -2px 12px rgba(0,0,0,.06);" +
      "display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap";
    banner.innerHTML =
      '🎁 免费试看中 · <a href="' + ZSXQ_URL +
      '" target="_blank" rel="noopener" style="color:#1AAD19;font-weight:700;text-decoration:none">加入知识星球 ¥888/年 →</a>' +
      ' · <span style="font-weight:400;color:#A0720A">仅此1份，下次需付费</span>';
    document.body.appendChild(banner);

    // ⭐ 关键：页面加载成功后再标记已使用（不在导航页提前消耗）
    window.addEventListener("load", () => {
      Paywall.useFreeView();
    });
    return;
  }

  // 无认证也无免费次数 → 弹付费墙（带关闭按钮）
  const title = document.title || "";
  Paywall.renderPaywall("paywall-container", title);
});
