/**
 * 蓝宝书Max · 付费墙鉴权系统
 * ==============================
 * 知识星球付费用户验证方案
 *
 * 原理：
 *   1. 你在知识星球付费群发布「访问码」
 *   2. 付费用户在此输入访问码
 *   3. 客户端 SHA-256 哈希比对（不传服务器，零泄露）
 *   4. 验证通过后 localStorage 持久化
 *
 * 如何更新访问码：
 *   1. 决定新码（如 BLUEBOOK-2026-Q3）
 *   2. 在终端运行: echo -n "新码" | shasum -a 256
 *   3. 把得到的 hash 加到下方 VALID_HASHES 数组
 *   4. 把旧 hash 留在数组中 7 天（给用户过渡期），然后删除
 *   5. 在知识星球群发新码
 */

// ===== 配置区 —— 在这里更新访问码哈希 =====
const VALID_HASHES = [
  // 初始访问码: BLUEBOOK-MAX-2026
  "062e06e81a413b0fbaf7151dddf1129ec4d50368ece1e233e3fa24a759c88bfa",
  // 添加更多 hash 以支持访问码轮换（旧码保留过渡期）
];

// 知识星球链接
const ZSXQ_URL = "https://t.zsxq.com/"; // 替换为你的知识星球链接
const ZSXQ_NAME = "蓝宝书Max投研圈";       // 替换为你的星球名称

// localStorage key
const AUTH_KEY = "bbmax_auth_v2";
const AUTH_CODE_KEY = "bbmax_auth_code";

// ===== 鉴权逻辑 =====

const Paywall = {
  /**
   * 检查是否已认证
   */
  isAuthenticated() {
    try {
      const auth = JSON.parse(localStorage.getItem(AUTH_KEY) || "{}");
      return auth.valid === true;
    } catch {
      return false;
    }
  },

  /**
   * 获取认证信息（用于显示、防泄露追踪）
   */
  getAuthInfo() {
    try {
      return JSON.parse(localStorage.getItem(AUTH_KEY) || "{}");
    } catch {
      return {};
    }
  },

  /**
   * 用 Web Crypto API 计算 SHA-256
   */
  async sha256(message) {
    const encoder = new TextEncoder();
    const data = encoder.encode(message);
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
  },

  /**
   * 验证访问码
   * @returns {{success: boolean, message: string}}
   */
  async verify(code) {
    if (!code || code.trim().length < 6) {
      return { success: false, message: "访问码格式不正确" };
    }

    const hash = await this.sha256(code.trim());

    if (VALID_HASHES.includes(hash)) {
      // 找到匹配的 hash 索引（用于防泄露标记）
      const hashIndex = VALID_HASHES.indexOf(hash);
      const authData = {
        valid: true,
        codeId: hashIndex,
        activatedAt: Date.now(),
        codePrefix: code.trim().substring(0, 2), // 只存前2位做标记
      };
      localStorage.setItem(AUTH_KEY, JSON.stringify(authData));
      return { success: true, message: "验证成功！欢迎加入蓝宝书Max" };
    }

    return { success: false, message: "访问码无效，请在知识星球付费群获取最新访问码" };
  },

  /**
   * 登出
   */
  logout() {
    localStorage.removeItem(AUTH_KEY);
  },

  /**
   * 渲染付费墙 UI（登录弹窗）
   * @param {string} containerId - 挂载点
   */
  renderPaywall(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
    <div class="pw-overlay" id="pw-overlay">
      <div class="pw-card">
        <div class="pw-icon">🔐</div>
        <h2 class="pw-title">知识星球付费会员专享</h2>
        <p class="pw-desc">
          蓝宝书Max 为付费订阅产品<br>
          请在「${ZSXQ_NAME}」知识星球获取访问码
        </p>

        <div class="pw-input-group">
          <input
            class="pw-input"
            type="text"
            id="pw-code-input"
            placeholder="输入访问码"
            autocomplete="off"
            maxlength="32"
          >
          <button class="pw-btn" id="pw-submit-btn">验证</button>
        </div>

        <div class="pw-error" id="pw-error"></div>

        <div class="pw-footer">
          <p>没有访问码？</p>
          <a href="${ZSXQ_URL}" target="_blank" rel="noopener" class="pw-zsxq-btn">
            🪐 加入知识星球，年费订阅
          </a>
        </div>
      </div>
    </div>`;

    // 事件绑定
    const input = document.getElementById("pw-code-input");
    const btn = document.getElementById("pw-submit-btn");
    const error = document.getElementById("pw-error");

    const doVerify = async () => {
      btn.disabled = true;
      btn.textContent = "验证中...";
      error.style.display = "none";

      const result = await Paywall.verify(input.value);
      if (result.success) {
        // 刷新页面，解锁内容
        window.location.reload();
      } else {
        error.textContent = result.message;
        error.style.display = "block";
        btn.disabled = false;
        btn.textContent = "验证";
        input.focus();
        input.select();
      }
    };

    btn.addEventListener("click", doVerify);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") doVerify();
    });

    // 自动聚焦
    setTimeout(() => input.focus(), 300);
  },

  /**
   * 渲染轻量锁图标（用于导航页列表项）
   * @returns HTML string
   */
  lockIcon() {
    return '<span class="pw-lock" title="付费会员专享">🔒</span>';
  },

  /**
   * 渲染已解锁标记
   */
  unlockBadge() {
    const info = this.getAuthInfo();
    return `<span class="pw-unlocked" title="已通过知识星球验证">✓ 已订阅</span>`;
  },
};

// 如果页面有 data-paywall="true" 属性，自动检测鉴权
document.addEventListener("DOMContentLoaded", () => {
  const needsAuth = document.documentElement.getAttribute("data-paywall") === "true";
  if (needsAuth && !Paywall.isAuthenticated()) {
    Paywall.renderPaywall("paywall-container");
  }
});
