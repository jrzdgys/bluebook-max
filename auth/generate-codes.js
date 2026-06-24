/**
 * 蓝宝书Max · 激活码批量生成工具
 * ==============================
 *
 * 用法:
 *   node generate-codes.js [数量] [过期天数]
 *
 * 示例:
 *   node generate-codes.js 10 365
 *   → 生成 10 个码，有效期 365 天
 */

const count = parseInt(process.argv[2]) || 5;
const days = parseInt(process.argv[3]) || 365;

const crypto = require('crypto');

function generate() {
  const rand = crypto.randomBytes(4).toString('hex').toUpperCase();
  return `BBM-${rand}`;
}

const codes = [];
for (let i = 0; i < count; i++) {
  let code;
  do { code = generate(); } while (codes.includes(code));
  codes.push(code);
}

const expires = new Date(Date.now() + days * 24 * 60 * 60 * 1000);

console.log(`// 蓝宝书Max 激活码 (${count}个, 有效期${days}天, 到期${expires.toISOString().slice(0,10)})`);
console.log('// 复制以下命令到 wrangler CLI 执行:\n');

codes.forEach(code => {
  const kvValue = JSON.stringify({
    devices: [],
    expiresAt: expires.toISOString(),
    createdAt: new Date().toISOString(),
  });
  console.log(`npx wrangler kv:key put --binding=AUTH_CODES "code:${code}" '${kvValue}'`);
});

console.log('\n// 或者用 curl:');
process.env.CF_API_TOKEN = process.env.CF_API_TOKEN || 'YOUR_API_TOKEN';
const accountId = process.env.CF_ACCOUNT_ID || 'YOUR_ACCOUNT_ID';
const kvId = process.env.CF_KV_ID || 'YOUR_KV_NAMESPACE_ID';

codes.forEach(code => {
  const kvValue = JSON.stringify({
    devices: [],
    expiresAt: expires.toISOString(),
    createdAt: new Date().toISOString(),
  });
  console.log(`curl -X PUT "https://api.cloudflare.com/client/v4/accounts/${accountId}/storage/kv/namespaces/${kvId}/values/code:${code}" \\`);
  console.log(`  -H "Authorization: Bearer ${process.env.CF_API_TOKEN}" \\`);
  console.log(`  -H "Content-Type: application/json" \\`);
  console.log(`  -d '${kvValue}'`);
});

console.log('\n---');
console.log('激活码列表:');
codes.forEach((c, i) => console.log(`${i + 1}. ${c}`));
