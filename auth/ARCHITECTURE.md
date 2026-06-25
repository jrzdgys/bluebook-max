# 蓝宝书Max · 鉴权系统架构文档 v4

> 本文档记录认证系统的完整架构、设计决策、已知问题和维护指南。  
> **最后更新**: 2026-06-25 | **当前版本**: v4（双通道并行验证）

---

## 目录

1. [系统架构总览](#一系统架构总览)
2. [核心流程](#二核心流程)
3. [双通道并行验证](#三双通道并行验证)
4. [iOS Safari 兼容方案](#四ios-safari-兼容方案)
5. [Token 设计](#五token-设计)
6. [中国区回退方案（HMAC 本地验证）](#六中国区回退方案hmac-本地验证)
7. [Worker API 端点](#七worker-api-端点)
8. [管理后台 admin.html](#八管理后台-adminhtml)
9. [已知问题与注意事项](#九已知问题与注意事项)
10. [维护清单](#十维护清单)

---

## 一、系统架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    用户浏览器 (paywall.js)                     │
│                                                             │
│  ┌──────────────┐    Promise.race     ┌──────────────────┐  │
│  │  Worker通道   │ ◄────────────────► │  本地HMAC回退    │  │
│  │  (Cloudflare) │   并行竞争          │  (auth-codes.json)│  │
│  └──────┬───────┘                     └────────┬─────────┘  │
│         │                                      │            │
└─────────┼──────────────────────────────────────┼────────────┘
          │ POST /activate                       │ HMAC-SHA256
          ▼                                      ▼
┌─────────────────────┐              ┌──────────────────────┐
│  bluebook-auth      │              │ GitHub Pages 静态文件  │
│  Cloudflare Worker  │              │ auth-codes.json       │
│  + KV (AUTH_CODES)  │              │ (预先签名的12个激活码) │
│  (境外可用)          │              │ (国内快速直连)        │
└─────────────────────┘              └──────────────────────┘
```

### 组件说明

| 组件 | 位置 | 职责 |
|------|------|------|
| `paywall.js` | GitHub Pages, 前端加载 | 设备指纹采集、双通道激活、Token 管理、弹窗 UI |
| `auth-worker.js` | Cloudflare Workers | 中心化鉴权、设备绑定、激活码管理、KV 存储 |
| `auth-codes.json` | GitHub Pages 静态文件 | 中国区回退方案，12 个预签名激活码 |
| `AUTH_CODES` (KV) | Cloudflare KV | Worker 端激活码存储（设备绑定状态） |
| `admin.html` | GitHub Pages | 激活码管理后台（依赖 Worker API） |

---

## 二、核心流程

### 2.1 页面加载鉴权

```
DOMContentLoaded
    │
    ▼
检查 data-paywall="true"？
    │
    ├── 否 → 跳过，显示内容
    │
    └── 是 → 检查 localStorage 中 Token
                │
                ├── Token 存在且未过期 → 添加 .bb-authenticated 类，显示内容
                │
                └── Token 不存在/过期 → 弹出激活弹窗
```

### 2.2 激活流程（双通道并行）

```
用户输入激活码 → 点击"激活账号"
    │
    ▼
收集设备指纹 (collectFingerprint)
    │
    ▼
发起 Promise.race ───────────────────┐
    │                                  │
    ▼                                  ▼
Worker 通道                       本地 HMAC 回退
POST /activate                    读取 auth-codes.json
超时：10s                          查询激活码 HMAC 签名
                                   验证签名 → 本地签发 Token
    │                                  │
    └────────── 谁先返回谁胜出 ─────────┘
                        │
                        ▼
                    Token 写入 localStorage
                    页面刷新 → 显示内容
```

---

## 三、双通道并行验证

### 3.1 为什么需要双通道

Cloudflare Workers 的 `workers.dev` 域名在**中国大陆被 GFW 封锁**，直接请求会导致 TCP 连接超时（约 20-30s）。早期版本采用串行方案（先等 Worker 超时再 fallback），导致中国区用户激活延迟高达 20s+。

### 3.2 并行方案（v4 核心改进）

```javascript
// paywall.js - 激活核心逻辑
activate: function(code) {
  var fp = this._fp;
  var workerPromise = fetch(WORKER_URL + '/activate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: AbortSignal.timeout(10000),  // Worker 10s 超时
    body: JSON.stringify({ code: code, fp: fp.hash })
  }).then(function(r) { return r.json(); });

  var localPromise = Paywall._verifyLocal(code);  // 本地 HMAC 验证 (~1s)

  return Promise.race([workerPromise, localPromise])
    .then(function(result) {
      if (result.ok) {
        localStorage.setItem(AUTH_KEY, result.token);
        var exp = parseInt(result.token.split('.')[2], 10);
        localStorage.setItem(EXPIRES_KEY, String(exp));
      }
      return result;
    });
}
```

### 3.3 超时策略

| 通道 | 超时时间 | 说明 |
|------|---------|------|
| Worker | 10s | `AbortSignal.timeout(10000)` |
| 本地 HMAC | ~1s | 纯本地计算，无网络依赖 |
| 激活按钮安全兜底 | 25s | `safetyTimer`，防止两个通道都失败时按钮永久 disabled |

### 3.4 安全兜底 (25s Timer)

```javascript
var safetyTimer = setTimeout(function() {
  btn.disabled = false;
  btn.textContent = '激活账号';
  showError('请求超时，请检查网络后重试');
}, 25000);
```

极端情况下（Worker 被墙 + auth-codes.json 加载失败 + 用户网络异常），25s 后自动恢复按钮状态。

---

## 四、iOS Safari 兼容方案

### 4.1 问题根因

`canvas.toDataURL()` 在 iOS WebKit 中**同步阻塞主线程**（所有浏览器：Safari、Chrome、微信内嵌浏览器均受影响）。私密模式下此问题更严重，可能导致页面完全卡死。

这是由于 iOS WebKit 的限制：Canvas 在私密模式下返回全空图像，且 `toDataURL()` 的同步编码过程阻塞主线程可达数秒。

### 4.2 解决方案

```javascript
function getCanvasHash() {
  return new Promise(function(resolve) {
    // iOS WebKit: toDataURL() 同步阻塞主线程，直接跳过
    if (/iPhone|iPad|iPod/i.test(navigator.userAgent)) {
      resolve('ios-skip-' + Date.now());
      return;
    }
    // 非 iOS 设备正常执行 canvas 指纹
    // ... canvas 绘制 + toDataURL + SHA256
  });
}
```

### 4.3 降级指纹组成

iOS 跳过 Canvas 后，使用 6 维稳定数据生成指纹：

```javascript
var stableParts = [
  navigator.userAgent,        // UA 字符串
  navigator.platform,         // 平台（iPhone/iPad）
  navigator.language,         // 语言偏好
  screen.width,               // 屏幕宽度
  screen.height,              // 屏幕高度
  window.devicePixelRatio,    // 像素比
  Intl.DateTimeFormat().resolvedOptions().timeZone  // 时区
].join('|||');
```

这些特征在 iOS 设备上足够区分不同用户，且不需要 Canvas 指纹。

### 4.4 Canvas 3s 超时保护（非 iOS 设备）

非 iOS 设备也设置了 3s 超时，防止罕见场景下的 Canvas 卡死：

```javascript
var timer = setTimeout(function() {
  resolve('canvas-timeout-' + Date.now());
}, 3000);
```

---

## 五、Token 设计

### 5.1 Token 格式

```
base64(指纹|时间戳|bbm2026) . 指纹 . 过期时间戳
   ├────── 载荷 ────────├  ├─ 验证 ─├  ├── 30 天有效期 ──┤
```

示例:
```
MWYyZDMyfDE3NTE4OTc2MDB8YmJtMjAyNg==.1f2d32.1751897600000
```

### 5.2 过期时间计算

```javascript
// ✅ 正确（当前线上版本）
var token = btoa(fp + '|' + Date.now() + '|bbm2026') + '.' + fp + '.' + (Date.now() + 86400000 * 30);

// ❌ 错误（v3 版本 bug，导致 Token 签发即过期）
var token = btoa(fp + '|' + Date.now() + '|bbm2026') + '.' + fp + '.' + Date.now();
//                                                                      ^^^^^^^^
//                                                                      Date.now() 是当前时间！
//                                                                      isAuthenticated() 比较时立即判为过期
```

### 5.3 本地 Token 验证

```javascript
isAuthenticated: function() {
  var token = localStorage.getItem(AUTH_KEY);
  if (!token) return false;
  var parts = token.split('.');
  if (parts.length !== 3) return false;
  var expiresAt = parseInt(parts[2], 10);
  if (isNaN(expiresAt)) return false;
  return Date.now() < expiresAt;  // 未过期
}
```

### 5.4 安全性说明

Token 设计目标是防篡改、防重放、支持离线验证：

- **防篡改**: Token 的 payload 中包含指纹，本地验证时取 `parts[1]` 与当前指纹比对
- **时效控制**: 过期时间戳明文存储，配合 `isAuthenticated()` 本地判断
- **签名**（Worker 端）: `btoa(fp + '|' + timestamp + '|bbm2026')` 作为简单签名层
- **注意**: 当前 Token 不是 JWT 标准格式，没有强签名验证。如果安全性要求更高，建议使用 `TOKEN_SECRET` 做 HMAC 签名

---

## 六、中国区回退方案（HMAC 本地验证）

### 6.1 设计动机

由于 Cloudflare Workers 的 `workers.dev` 域名在中国大陆无法访问，需要一个**不依赖境外服务器的激活方案**。

### 6.2 架构

```
GitHub Pages 托管
auth-codes.json (12个预签名激活码)
        │
        ▼
浏览器 fetch(auth-codes.json)  ← 国内 CDN 直连（快）
        │
        ▼
HMAC-SHA256 验证签名
        │
        ▼
验证通过 → 本地签发 Token → 写入 localStorage
```

### 6.3 auth-codes.json 格式

```json
{
  "v": 1,
  "entries": [
    { "c": "BBM-0299F91C", "h": "25a8aa5a2542e679edc38b87acd939f6" },
    { "c": "BBM-0ED6F6C9", "h": "d8fe7a79c0c604fdac16a01b3530dcda" }
  ],
  "gen": "2026-06-25"
}
```

- `c`: 激活码
- `h`: HMAC-SHA256(secret, code) 截断前 32 位十六进制
- 签名密钥: `bbm-fallback-v1-client-key-2026`

### 6.4 本地验证逻辑

```javascript
_verifyLocal: function(code) {
  return fetch(AUTH_CODES_URL)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var entry = data.entries.find(function(e) { return e.c === code; });
      if (!entry) return { ok: false, error: '无效激活码' };
      return sha256(code + '|' + FALLBACK_SECRET).then(function(hash) {
        if (hash.substring(0, 32) !== entry.h) return { ok: false, error: '激活码验证失败' };
        var fp = Paywall._fp.hash;
        var token = btoa(fp + '|' + Date.now() + '|bbm-local') + '.' + fp + '.' + (Date.now() + 86400000 * 30);
        return { ok: true, token: token, message: '验证通过（本地）' };
      });
    });
}
```

### 6.5 安全限制

| 限制项 | 说明 |
|--------|------|
| 激活码数量 | 当前 12 个（可扩展） |
| 设备绑定 | ❌ 本地回退**不做**设备绑定（无后端状态） |
| 抗重放 | 同一激活码可被多个设备使用 |
| 防篡改 | HMAC 签名防止伪造激活码 |

**注意**: 本地回退本质是**信任代理方案**——信任 GitHub Pages 源文件不被篡改。如果 auth-codes.json 泄露，任何知道 HMAC 密钥的人都可以伪造激活码。正式分发时，建议回收本地回退码，仅保留 Worker 通道。

---

## 七、Worker API 端点

### 7.1 端点一览

| 路径 | 方法 | 用途 | Admin 保护 |
|------|------|------|-----------|
| `/activate` | POST | 激活码绑定设备 | ❌ |
| `/verify` | POST | 验证 Token 有效性 | ❌ |
| `/unbind` | POST | 解绑设备（指定 fp 或全部） | ✅ `admin_key` |
| `/list` | POST | 列出所有激活码状态 | ✅ `admin_key` |
| `/codes/create` | POST | 批量创建激活码 | ✅ `admin_key` |
| `/codes/delete` | POST | 删除激活码 | ✅ `admin_key` |

### 7.2 Worker 配置

| 配置项 | 值 |
|--------|-----|
| Worker URL | `https://bluebook-auth.bluebookmax.workers.dev` |
| KV 绑定变量名 | `AUTH_CODES` |
| KV Namespace ID | `e10fae5c8642470f8fa57cfae7124ed8` |
| 形态 | Service Worker (`addEventListener('fetch', ...)`) |
| TOKEN_SECRET | 环境变量存储（64位 hex） |
| ADMIN_KEY | 环境变量（当前: `bbm-admin-2y0jPFwxk2MZQTfR`） |
| 最大设备数/码 | 2 |

### 7.3 设备绑定策略

```
┌──────────────┐
│  新激活码     │ → fingerprint=null → 绑定当前设备
│  devices=0    │
└──────────────┘
       │
       ▼
┌──────────────┐
│  指纹匹配     │ → 已有设备 → 验证通过
│  devices≥1    │
└──────────────┘
       │
       ▼
┌──────────────┐
│  指纹不匹配   │
│  devices<2   │ → 新增设备（第二台）
└──────────────┘
       │
       ▼
┌──────────────┐
│  指纹不匹配   │
│  devices≥2   │ → 拒绝：已达最大设备数
└──────────────┘
```

---

## 八、管理后台 admin.html

### 8.1 位置

- GitHub Pages: `https://jrzdgys.github.io/bluebook-max/admin.html`
- 源码: `/auth/admin.html`

### 8.2 功能

- 查看激活码列表（已绑定/未使用/设备数）
- 按激活码搜索
- 批量生成新激活码
- 删除激活码
- 解绑设备

### 8.3 访问密码

- 密码: 由 `ADMIN_KEY` 控制
- 前端登录后显示订阅到期日
- 密码找回功能（待实现）

---

## 九、已知问题与注意事项

### 9.1 部署缓存

| 资源 | 缓存策略 | 更新方式 |
|------|---------|---------|
| `paywall.js` | GitHub Pages CDN ~5-10min | `?v=N` 缓存破坏 |
| `auth-codes.json` | GitHub Pages CDN ~5-10min | `?v=` + `Date.now()` |
| `auth-worker.js` | Cloudflare 即时部署 | Worker 编辑后保存 |
| `admin.html` | GitHub Pages CDN ~5-10min | 等待缓存刷新 |

### 9.2 iOS 测试须知

1. **必须清除 Safari 缓存**（设置 → Safari → 清除历史记录与网站数据）
2. 微信内嵌浏览器也需要清除缓存
3. `paywall.js?v=4` 可能仍被缓存，建议用 `?v=` + `Date.now()` 或使用 `raw.githubusercontent.com` 的非缓存版本

### 9.3 Cloudflare Dashboard 注意事项

- Dashboard 代码编辑器在 Worker 创建后默认显示 **ES module 格式**，但当前部署的是 **Service Worker 格式**
- 不要在 Dashboard 编辑器中点击"保存"，否则会用 ES module 格式覆盖当前代码
- 如需修改，编辑 `auth-worker.js` 后通过 Wrangler CLI 或 API 重新部署

### 9.4 Token 安全

当前 Token 使用简单的 Base64 编码，未使用 `TOKEN_SECRET` 签名。如需加强安全：

```javascript
// 建议：使用 TOKEN_SECRET + HMAC-SHA256 签名
var payload = fp + '|' + Date.now();
var signature = hmacSHA256(payload, TOKEN_SECRET);
var token = btoa(payload) + '.' + btoa(signature) + '.' + (Date.now() + 86400000 * 30);
```

### 9.5 激活码管理

- 当前激活码 BBM-0299F91C 处于 `devices=0` 状态，可用于用户激活
- 测试码（TEST-*, ZZZ-*）和已删除的码已从 KV 清理
- KV 中空指纹条目保留，方便批量创建

---

## 十、维护清单

### 发布新版本

- [ ] 修改 `paywall.js`（如需）
- [ ] 修改 `auth-worker.js` 并重新部署到 Cloudflare
- [ ] 更新 `auth-codes.json`（如需添加本地回退码）
- [ ] 更新 `index.html` 中的 `paywall.js?v=N` 版本号
- [ ] 提交到 GitHub 并等待 CDN 刷新
- [ ] 通过 `raw.githubusercontent.com` 验证文件内容
- [ ] 在真机上测试（iOS + 桌面）

### 环境变量管理

| 变量 | 位置 | 更新方式 |
|------|------|---------|
| `ADMIN_KEY` | Cloudflare Worker 环境变量 | Dashboard → Worker → 设置 → 环境变量 |
| `TOKEN_SECRET` | Cloudflare Worker 环境变量 | Dashboard → Worker → 设置 → 环境变量 |
| `FALLBACK_SECRET` | `paywall.js` 硬编码 | 直接修改 JS 并重新部署 |

### 紧急回退

如果 Worker 出现故障：

1. 确保 `auth-codes.json` 中的激活码在 KV 中也有记录（双向同步）
2. 本地回退通道自动生效（不需要前端更新）
3. 修复 Worker 后通过 `raw.githubusercontent.com` 验证

---

> **版本历史**
> - v1 (初始): 纯 Worker 通道，无本地回退
> - v2: 加入 Canvas 指纹和 localStorage Token 缓存
> - v3: 加入中国区回退（串行：先等 Worker 超时再 fallback）
> - **v4 (当前)**: 双通道并行验证 + iOS Canvas 跳过 + Token 30天修复 + 25s 安全兜底 + DOM 弹窗重写
