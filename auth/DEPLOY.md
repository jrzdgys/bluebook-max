# 蓝宝书Max · 鉴权系统部署指南

## 一、Cloudflare Worker 部署

### 方式 A：通过 Dashboard（推荐，无需 CLI）

1. 打开 [Cloudflare Dashboard → Workers & Pages](https://dash.cloudflare.com/bfbe5adb75860529c469ce5316dd0072/workers-and-pages)
2. 点击「创建应用程序」→「Worker」
3. 名称填写 `bluebook-auth`
4. 删除默认代码，粘贴 `auth-worker.js` 的完整内容
5. 点击「保存并部署」

### 方式 B：通过 Wrangler CLI

```bash
cd auth/
npm install wrangler --save-dev
npx wrangler login
npx wrangler deploy
```

## 二、创建 KV 命名空间

### 通过 Dashboard
1. 进入 `bluebook-auth` Worker →「设置」→「KV 命名空间绑定」
2. 点击「添加绑定」
3. 变量名称：`AUTH_CODES`
4. 创建命名空间：`bluebook-auth-codes`
5. 保存

### 通过 CLI
```bash
npx wrangler kv namespace create AUTH_CODES
# 把输出的 ID 填入 wrangler.toml
npx wrangler deploy
```

## 三、设置环境变量

在 Worker →「设置」→「环境变量」中添加：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `ADMIN_KEY` | 管理员密钥（用于解绑设备） | `bbm-admin-$(openssl rand -hex 16)` |
| `TOKEN_SECRET` | Token 签名密钥（64位随机） | `$(openssl rand -hex 32)` |

⚠️ **两个密钥务必填写复杂随机值，部署后立即保存。**

## 四、生成激活码

```bash
cd auth/
node generate-codes.js 10 365
```

输出示例：
```
1. BBM-A1B2C3D4
2. BBM-E5F6G7H8
...
```

将输出中的 `wrangler kv:key put` 命令逐条执行，
或复制 KV 数据后通过 Dashboard → KV → 手动添加。

## 五、更新前端配置

生成 Worker 后，获取 Worker 地址：
`https://bluebook-auth.<你的子域名>.workers.dev`

编辑 `paywall.js`，找到：
```js
const WORKER_URL = "https://bluebook-auth.你的用户名.workers.dev";
```

改为实际的 Worker 地址。

## 六、验证

### 激活测试
```bash
curl -X POST https://bluebook-auth.xxx.workers.dev/activate \
  -H "Content-Type: application/json" \
  -d '{"code":"BBM-A1B2C3D4","fp":"test-fingerprint-hash"}'
# 期望返回: { "ok": true, "token": "..." }
```

### 验证 Token
```bash
curl -X POST https://bluebook-auth.xxx.workers.dev/verify \
  -H "Content-Type: application/json" \
  -d '{"token":"<上一步返回的token>"}'
# 期望返回: { "ok": true, "fp": "...", "expires": ... }
```

## 七、管理命令

### 查看所有已使用的激活码
```bash
# 通过 Dashboard → KV 浏览
```

### 解绑指定设备
```bash
curl -X POST https://bluebook-auth.xxx.workers.dev/unbind \
  -H "Content-Type: application/json" \
  -d '{"admin_key":"你的ADMIN_KEY","code":"BBM-A1B2C3D4","fp":"待解绑的设备指纹"}'
```

### 解绑全部设备（重置码）
```bash
curl -X POST https://bluebook-auth.xxx.workers.dev/unbind \
  -H "Content-Type: application/json" \
  -d '{"admin_key":"你的ADMIN_KEY","code":"BBM-A1B2C3D4"}'
```
