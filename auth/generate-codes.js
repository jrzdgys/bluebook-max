/**
 * 蓝宝书Max · 激活码批量生成工具
 * ==============================
 *
 * 用法:
 *   node generate-codes.js [数量] [过期天数]
 *
 * 示例:
 *   node generate-codes.js 10 365
 *   → 生成 10 个码（随机8位数字），有效期 365 天
 */

const count = parseInt(process.argv[2]) || 5;
const days = parseInt(process.argv[3]) || 365;

function generate() {
  // 生成随机8位数字
  return String(10000000 + Math.floor(Math.random() * 90000000));
}

const codes = [];
const seen = new Set();
for (let i = 0; i < count; i++) {
  let code;
  do { code = generate(); } while (seen.has(code));
  seen.add(code);
  codes.push(code);
}

const expires = new Date(Date.now() + days * 24 * 60 * 60 * 1000);

console.log('// 蓝宝书Max 激活码 (' + count + '个, 有效期' + days + '天, 到期' + expires.toISOString().slice(0, 10) + ')');
console.log('// 随机8位数字格式');
console.log('');

codes.forEach(code => {
  const kvValue = JSON.stringify({
    devices: [],
    expiresAt: expires.toISOString(),
    createdAt: new Date().toISOString(),
  });
  console.log("curl -X PUT \"https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/storage/kv/namespaces/${CF_KV_ID}/values/code:" + code + "\" \\");
  console.log('  -H "Authorization: Bearer ${CF_API_TOKEN}" \\');
  console.log('  -H "Content-Type: application/json" \\');
  console.log("  -d '" + kvValue + "'");
});

console.log('');
console.log('---');
console.log('激活码列表:');
codes.forEach((c, i) => console.log((i + 1) + '. ' + c));
