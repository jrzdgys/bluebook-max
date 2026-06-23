/**
 * 蓝宝书Max · 付费墙鉴权系统 v3
 * ==============================
 * 
 * 鉴权流程：
 *   导航页（index.html）    → 完全开放，不弹付费墙（广告展示）
 *   报告页（reports/*.html） → 首次打开免费试看 1 份
 *                           → 之后弹出付费墙，需输入访问码
 * 
 * 访问码管理：
 *   打开 admin.html → 输入新码 → 复制哈希 → 粘贴到 codes.js → 部署
 * 
 * 星球信息：
 *   蓝宝书Max · https://t.zsxq.com/6iVvp
 */

// ===== 配置 =====
const ZSXQ_URL = "https://t.zsxq.com/6iVvp";
const ZSXQ_NAME = "蓝宝书Max";

const AUTH_KEY = "bbmax_auth_v3";
const FREE_VIEW_KEY = "bbmax_free_view_v3";

// ===== 鉴权逻辑 =====
const Paywall = {

  // ---------- 认证 ----------
  isAuthenticated() {
    try {
      const auth = JSON.parse(localStorage.getItem(AUTH_KEY) || "{}");
      return auth.valid === true;
    } catch { return false; }
  },

  getAuthInfo() {
    try { return JSON.parse(localStorage.getItem(AUTH_KEY) || "{}"); }
    catch { return {}; }
  },

  // ---------- 免费试看 ----------
  hasFreeView() {
    return !localStorage.getItem(FREE_VIEW_KEY);
  },

  useFreeView() {
    localStorage.setItem(FREE_VIEW_KEY, Date.now().toString());
    // 7 天后重置免费试看（让回头客可以再看一眼）
    // 注：这行在 localStorage 中，用户清缓存可重置，这是故意的——降低流失率
  },

  // ---------- SHA-256 ----------
  async sha256(message) {
    const encoder = new TextEncoder();
    const data = encoder.encode(message);
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
  },

  // ---------- 验证 ----------
  async verify(code) {
    if (!code || code.trim().length < 4) {
      return { success: false, message: "访问码格式不正确" };
    }
    const hash = await this.sha256(code.trim());
    if (VALID_HASHES.includes(hash)) {
      const idx = VALID_HASHES.indexOf(hash);
      localStorage.setItem(AUTH_KEY, JSON.stringify({
        valid: true, codeId: idx, activatedAt: Date.now(),
        codePrefix: code.trim().substring(0, 2),
      }));
      return { success: true, message: "验证成功！欢迎加入蓝宝书Max" };
    }
    return { success: false, message: "访问码无效，请在知识星球「蓝宝书Max」获取最新码" };
  },

  logout() {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(FREE_VIEW_KEY);
  },

  // ---------- 付费墙 UI ----------
  renderPaywall(containerId, title) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const reportTitle = title || document.title || "";
    const isReport = containerId === "paywall-container";

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
          margin:auto;
        }
        .pw-card2 .pw-icon2{font-size:44px;margin-bottom:12px}
        .pw-card2 h2{font-size:20px;font-weight:700;color:#1D1D1F;margin-bottom:8px}
        .pw-card2 .pw-desc2{font-size:13px;color:#86868B;line-height:1.6;margin-bottom:24px}
        .pw-card2 .pw-input2{
          width:100%;padding:12px 16px;border:1.5px solid #E5E5EA;border-radius:12px;
          font-size:15px;font-family:inherit;text-align:center;letter-spacing:1px;
          outline:none;transition:border-color .15s;margin-bottom:10px;
        }
        .pw-card2 .pw-input2:focus{border-color:#0071E3}
        .pw-card2 .pw-btn2{
          width:100%;padding:12px;background:#0071E3;color:#fff;border:none;
          border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;
          font-family:inherit;transition:all .15s;
        }
        .pw-card2 .pw-btn2:hover{background:#0077ED}
        .pw-card2 .pw-btn2:disabled{opacity:.6;cursor:not-allowed}
        .pw-card2 .pw-err2{color:#FF3B30;font-size:12px;margin-top:8px;display:none}
        .pw-card2 .pw-ft2{
          margin-top:24px;padding-top:20px;border-top:1px solid #F2F2F7;
          font-size:12px;color:#AEAEB2;
        }
        .pw-card2 .pw-ft2 a{
          display:inline-flex;align-items:center;gap:6px;margin-top:10px;
          padding:10px 24px;background:linear-gradient(135deg,#1AAD19,#0F8F0F);
          color:#fff;border-radius:12px;text-decoration:none;
          font-size:13px;font-weight:600;transition:all .15s;
        }
        .pw-card2 .pw-ft2 a:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(26,173,25,.3)}
      </style>
      <div class="pw-card2">
        <div class="pw-icon2">🔐</div>
        <h2>知识星球付费会员专享</h2>
        <p class="pw-desc2">
          ${reportTitle}<br>
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

    const input = document.getElementById("pw-code-input2");
    const btn = document.getElementById("pw-submit-btn2");
    const err = document.getElementById("pw-error2");

    const doVerify = async () => {
      btn.disabled = true;
      btn.textContent = "验证中...";
      err.style.display = "none";
      const result = await Paywall.verify(input.value);
      if (result.success) {
        window.location.reload();
      } else {
        err.textContent = result.message;
        err.style.display = "block";
        btn.disabled = false;
        btn.textContent = "验证访问码";
        input.focus(); input.select();
      }
    };
    btn.addEventListener("click", doVerify);
    input.addEventListener("keydown", e => { if (e.key === "Enter") doVerify(); });
    setTimeout(() => input.focus(), 300);
  },

  // ---------- 装饰 ----------
  lockIcon() { return '<span style="font-size:14px;margin-left:4px;opacity:.5">🔒</span>'; },
  unlockBadge() {
    return '<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;background:#EEFFF2;color:#34C759;border-radius:100px;font-size:11px;font-weight:600">✓ 已订阅</span>';
  },
};

// ===== 页面自动检测 =====
document.addEventListener("DOMContentLoaded", () => {
  const needsAuth = document.documentElement.getAttribute("data-paywall") === "true";
  if (!needsAuth) return;

  // 已认证 → 直接放行
  if (Paywall.isAuthenticated()) {
    document.documentElement.classList.add("bb-authenticated");
    return;
  }

  // 有免费试看次数 → 放行
  if (Paywall.hasFreeView()) {
    Paywall.useFreeView();
    document.documentElement.classList.add("bb-free-view");

    // 显示一个提示条，告知这是免费试看
    const banner = document.createElement("div");
    banner.style.cssText = "position:fixed;bottom:0;left:0;right:0;z-index:9999;" +
      "background:linear-gradient(135deg,#FFF9F0,#FFF0E0);" +
      "color:#C47A00;text-align:center;padding:10px 16px;" +
      "font-size:13px;font-weight:600;box-shadow:0 -2px 12px rgba(0,0,0,.06);" +
      "display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap";
    banner.innerHTML = '🎁 免费试看中 · 本份报告可免费查看 · <a href="' + ZSXQ_URL +
      '" target="_blank" rel="noopener" style="color:#1AAD19;font-weight:700;text-decoration:none">加入知识星球 ¥888/年 →</a>';
    document.body.appendChild(banner);
    return;
  }

  // 无认证也无免费次数 → 弹付费墙
  const title = document.title || "";
  Paywall.renderPaywall("paywall-container", title);
});
