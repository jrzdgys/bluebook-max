#!/usr/bin/env python3
"""
蓝宝书Max · 自动生成器 v1 🔒
模板版本: am-20260622-live.html 锁定
支持四版: 晨会(am) / 午间(md) / 晚间(pm) / 全球(gl)
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

# === 版本配置 ===
EDITION_CONFIG = {
    "am": {"name": "晨会版", "badge": "国内版🧡", "badgeClass": "domestic", "time": "7:00"},
    "md": {"name": "午间版", "badge": "国内版🧡", "badgeClass": "domestic", "time": "12:00"},
    "pm": {"name": "晚间版", "badge": "国内版🧡", "badgeClass": "domestic", "time": "20:00"},
    "gl": {"name": "全球版", "badge": "全球版💙", "badgeClass": "global", "time": "8:00"},
}

# === A股代码映射（已验证 · 锁定 · 2026-06-22） ===
STOCK_CODES = {
    # AI上游材料全面涨价
    "中瓷电子":"sz003031","国瓷材料":"sz300285","中钨高新":"sz000657",
    "鼎泰高科":"sz301377","生益科技":"sh600183","国际复材":"sz301526",
    "宏和科技":"sh603256","铜冠铜箔":"sz301217","德福科技":"sz301511",
    "光华科技":"sz002741","天承科技":"sh688603",
    # 存储芯片
    "兆易创新":"sh603986","普冉股份":"sh688766","江波龙":"sz301308",
    "香农芯创":"sz300475","佰维存储":"sh688525","国科微":"sz300672",
    "风华高科":"sz000636","三环集团":"sz300408",
    # 半导体设备出海
    "北方华创":"sz002371","中微公司":"sh688012","盛美上海":"sh688082",
    "拓荆科技":"sh688072","长川科技":"sz300604","华峰测控":"sh688200",
    "富创精密":"sh688409","新莱应材":"sz301187","京仪装备":"sh688115",
    "珂玛科技":"sz301130",
    # 光纤藤仓涨价
    "中天科技":"sh600522","长飞光纤":"sh601869","亨通光电":"sh600487",
    "太辰光":"sz300570","永鼎股份":"sh600105","烽火通信":"sh600498",
    # 智谱GLM
    "海光信息":"sh688041","寒武纪":"sh688256","中科曙光":"sh603019",
    "润建股份":"sz002929","亚康股份":"sz301085",
    # MLCC
    "洁美科技":"sz002859","商络电子":"sz300975","雅创电子":"sz301099",
    # CoWoS玻璃基板
    "帝尔激光":"sz300776","芯碁微装":"sh688630","德龙激光":"sh688170",
    "东威科技":"sh688700","沃格光电":"sz300747","京东方A":"sz000725",
    "凯盛科技":"sh600552","戈碧迦":"bj835438","鼎龙股份":"sz300054",
    # 氧化钇断供
    "爱迪特":"sz301580","三祥新材":"sh603663","盛和资源":"sh600392",
    "金博股份":"sh688598","东方锆业":"sz002167",
    # 端午旅游
    "中国中免":"sh601888","长白山":"sh603099","峨眉山A":"sz000888",
    "宋城演艺":"sz300144","黄山旅游":"sh600054","锦江酒店":"sh600754",
    # 二手房
    "保利发展":"sh600048","滨江集团":"sz002244","我爱我家":"sz000560",
    "中国国贸":"sh600007","张江高科":"sh600895",
    # 算力租赁
    "弘信电子":"sz300657","软通动力":"sz301236","宏景科技":"sz301396",
    "协创数据":"sz300857","润泽科技":"sz300442",
    # 赛力斯机器人
    "浙江荣泰":"sh603119","恒立液压":"sh601100","斯菱智驱":"sz301550",
    "恒帅股份":"sz300969","宁波华翔":"sz002048","福赛科技":"sz301529",
    "岱美股份":"sh603730","日盈电子":"sh603286",
    # 功率半导体
    "扬杰科技":"sz300373","新洁能":"sh605111","华润微":"sh688396",
    "士兰微":"sh600460","捷捷微电":"sz300623","斯达半导":"sh603290",
    # 垣信卫星
    "上海瀚讯":"sz300762","信科移动":"sh688387","信维通信":"sz300136",
    "通宇通讯":"sz002792","臻镭科技":"sh688270","铖昌科技":"sz300782",
    "华测导航":"sz300627",
    # AIDC液冷
    "申菱环境":"sz301018","英维克":"sz002837","飞龙股份":"sz002536",
    "领益智造":"sz002600","大元泵业":"sh603757","奕东电子":"sz301123",
    "鼎通科技":"sh688668","川润股份":"sz002272",
    # 自免/医药
    "恒瑞医药":"sh600276","三生国健":"sh688336",
    # 压电陶瓷
    "星源材质":"sz300568","宁德时代":"sz300750","恩捷股份":"sz002812",
    "佛塑科技":"sz000973",
    # 陆家嘴论坛
    "中信证券":"sh600030","华泰证券":"sh601688",
    "中国人寿":"sh601628","中国平安":"sh601318",
    # 机会前瞻
    "兴业科技":"sz002468","厦门钨业":"sh600549","章源钨业":"sz002378",
    "中船特气":"sh688146",
    # 扩展A股池
    "三一重工":"sh600031","中国船舶":"sh600150","巨化股份":"sh600160",
    "万华化学":"sh600309","华鲁恒升":"sh600426","通威股份":"sh600438",
    "中国动力":"sh600482","贵州茅台":"sh600519","长电科技":"sh600584",
    "新安股份":"sh600596","老凤祥":"sh600612","中船防务":"sh600685",
    "均胜电子":"sh600699","安徽合力":"sh600761","航天电子":"sh600879",
    "隆基绿能":"sh601012","四方股份":"sh601126","工业富联":"sh601138",
    "中国西电":"sh601179","桐昆股份":"sh601233","拓普集团":"sh601689",
    "中国卫通":"sh601698","福莱特":"sh601865","亚星锚链":"sh601890",
    "紫金矿业":"sh601899","中国汽研":"sh601965","北特科技":"sh603009",
    "新泉股份":"sh603179","迎驾贡酒":"sh603198","上海洗霸":"sh603200",
    "新凤鸣":"sh603225","药明康德":"sh603259","华勤技术":"sh603296",
    "杭叉集团":"sh603298","浙江鼎力":"sh603338","龙旗科技":"sh603341",
    "今世缘":"sh603369","三美股份":"sh603379","九洲药业":"sh603456",
    "巨星农牧":"sh603477","韦尔股份":"sh603501","永艺股份":"sh603600",
    "五洲新春":"sh603667","华友钴业":"sh603799","福斯特":"sh603806",
    "欧派家居":"sh603833","瑞芯微":"sh603893","金徽酒":"sh603919",
    "洛阳钼业":"sh603993","神农集团":"sh605296",
    "容百科技":"sh688005","华依科技":"sh688071","虹软科技":"sh688088",
    "开普云":"sh688228","豪威集团":"sh688322","华虹半导体":"sh688347",
    "国博电子":"sh688375","源杰科技":"sh688498","华海诚科":"sh688535",
    "高华科技":"sh688539","中科星图":"sh688568","恒玄科技":"sh688608",
    "华丰科技":"sh688629","厦钨新能":"sh688778","中芯国际":"sh688981",
    "神州数码":"sz000034","中联重科":"sz000157","美的集团":"sz000333",
    "徐工机械":"sz000425","山推股份":"sz000680","五粮液":"sz000858",
    "华工科技":"sz000988","三花智控":"sz002050","天康生物":"sz002100",
    "通富微电":"sz002156","歌尔股份":"sz002241","拓维信息":"sz002261",
    "水晶光电":"sz002273","潮宏基":"sz002345","巨星科技":"sz002444",
    "赣锋锂业":"sz002460","沪电股份":"sz002463","天齐锂业":"sz002466",
    "立讯精密":"sz002475","德昌电机":"sz002498","比亚迪":"sz002594",
    "牧原股份":"sz002714","周大生":"sz002867","深南电路":"sz002916",
    "德赛西威":"sz002920","鹏鼎控股":"sz002938",
    "特锐德":"sz300001","汉威科技":"sz300007","当升科技":"sz300073",
    "拓尔思":"sz300229","阳光电源":"sz300274","中际旭创":"sz300308",
    "天孚通信":"sz300394","昆仑万维":"sz300418","先导智能":"sz300450",
    "胜宏科技":"sz300476","温氏股份":"sz300498","新易盛":"sz300502",
    "寒锐钴业":"sz300618","圣邦股份":"sz300661","康龙化成":"sz300759",
    "卓胜微":"sz300782","浩洋股份":"sz300833",
    "匠心家居":"sz301061","大族数控":"sz301200","腾远钴业":"sz301219",
    "致欧科技":"sz301376","安培龙":"sz301413","纳科诺尔":"sz832522",
}


def fetch_stock_prices(codes_batch):
    """从腾讯API获取股票行情"""
    try:
        url = f"http://qt.gtimg.cn/q={','.join(codes_batch)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("gbk", errors="replace")
    except Exception as e:
        print(f"  ⚠ 腾讯API请求失败: {e}")
        return {}

    prices = {}
    for line in raw.strip().split("\n"):
        if "~" not in line:
            continue
        parts = line.split("~")
        if len(parts) < 5:
            continue
        code = parts[2]
        try:
            price = float(parts[3])
            prev_close = float(parts[4])
        except (ValueError, IndexError):
            continue
        if prev_close > 0:
            pct = round((price - prev_close) / prev_close * 100, 2)
        else:
            pct = 0
        prices[code] = {"price": price, "pct": pct}
    return prices


def get_all_prices(stock_codes):
    """批量获取全部股票行情"""
    all_prices = {}
    codes = list(stock_codes.values())
    batch_size = 50
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        batch_prices = fetch_stock_prices(batch)
        all_prices.update(batch_prices)
        if i + batch_size < len(codes):
            time.sleep(0.3)
    return all_prices


def gen_secid_map(stock_codes):
    """生成东方财富 SECID_MAP（名称→secid）"""
    prefix_map = {"sh": "1", "sz": "0", "bj": "0"}
    lines = []
    for name, code in sorted(stock_codes.items()):
        mkt = code[:2]
        num = code[2:]
        prefix = prefix_map.get(mkt, "0")
        secid = f"{prefix}.{num}"
        lines.append(f'  "{name}": "{secid}"')
    return "const SECID_MAP = {\n" + ",\n".join(lines) + "\n};"


def generate_html(edition, today_str, prices):
    """基于锁定模板生成HTML"""
    edition_info = EDITION_CONFIG[edition]
    edition_name = edition_info["name"]
    date_display = f"{today_str[:4]}年{today_str[4:6]}月{today_str[6:8]}日"

    # 生成SECID_MAP
    secid_map_js = gen_secid_map(STOCK_CODES)

    # 计算涨跌统计
    up_count = sum(1 for p in prices.values() if p["pct"] > 0)
    down_count = sum(1 for p in prices.values() if p["pct"] < 0)
    total = len(prices)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>蓝宝书Max · {date_display} {edition_name}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;background:#E4E1DC;color:#2c2c2c;line-height:1.6;-webkit-font-smoothing:antialiased}}
.w{{max-width:900px;margin:0 auto;padding:16px}}
.sh{{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);color:#fff;padding:24px 20px;border-radius:12px 12px 0 0;text-align:center;position:relative}}
.sh h1{{font-size:22px;font-weight:700;letter-spacing:.5px}}
.sh h1 span{{color:#FFD700}}
.sh .sub{{font-size:13px;opacity:.75;margin-top:6px}}
.sh .badge{{display:inline-block;background:{'#EDE4DC' if edition in ('am','md','pm') else '#DEE5F7'};color:{'#7B5B3A' if edition in ('am','md','pm') else '#3A4F7B'};font-size:11px;padding:3px 10px;border-radius:20px;margin:8px 4px 0;font-weight:600}}
.sh .live-dot{{display:inline-block;width:8px;height:8px;background:#00E676;border-radius:50%;margin-left:8px;animation:pulse 2s infinite;vertical-align:middle}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.sh .stats{{display:flex;justify-content:center;gap:24px;margin-top:14px;font-size:13px;flex-wrap:wrap}}
.sh .stats span{{opacity:.85}}
.sh .stats .up{{color:#FF6B6B}}
.sh .stats .down{{color:#8FBC8F}}
.ct{{background:#FDFCF9;border-radius:0 0 12px 12px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,.06)}}
.summary-card{{background:linear-gradient(135deg,#f8f6f0,#f0ece4);border-radius:10px;padding:16px 20px;margin-bottom:20px;border-left:4px solid #C4433A}}
.summary-card h3{{font-size:15px;color:#555;margin-bottom:8px}}
.summary-one-liner{{font-size:14px;color:#333;line-height:1.5}}
.summary-meta{{display:flex;gap:16px;margin-top:8px;font-size:12px;color:#888;flex-wrap:wrap}}
.grid{{display:grid;grid-template-columns:1fr;gap:14px;margin-bottom:20px}}
.tcard{{background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 6px rgba(0,0,0,.05);border:1px solid #eee;position:relative}}
.tcard.opp{{border-left:4px solid #7C4FC4}}
.tcard.opp::before{{content:"🔮";position:absolute;top:12px;right:14px;font-size:18px}}
.tr{{display:inline-block;background:#C4433A;color:#fff;font-size:11px;padding:2px 10px;border-radius:4px;font-weight:700;margin-bottom:8px}}
.tname{{font-size:17px;font-weight:700;color:#1a1a2e;margin-bottom:6px}}
.state-badge{{display:inline-block;font-size:11px;padding:2px 8px;border-radius:4px;margin-left:8px;font-weight:600}}
.state-badge.main{{background:#FFF0F0;color:#C4433A}}
.state-badge.strong{{background:#FFF3E8;color:#E87A20}}
.state-badge.cont{{background:#EEF0FF;color:#3E54CE}}
.state-badge.hatch{{background:#F3EEFF;color:#7C4FC4}}
.ts{{margin:8px 0;font-size:13px;display:flex;align-items:center;gap:6px}}
.tsv{{font-weight:700;color:#C4433A;cursor:pointer;position:relative}}
.tsv:hover .hp{{display:block}}
.hp{{display:none;position:absolute;bottom:100%;left:0;background:#1a1a2e;color:#fff;padding:10px 14px;border-radius:8px;font-size:12px;white-space:nowrap;z-index:10;box-shadow:0 4px 16px rgba(0,0,0,.3)}}
.hp::after{{content:"";position:absolute;top:100%;left:16px;border:6px solid transparent;border-top-color:#1a1a2e}}
.t-reason{{font-size:13px;color:#555;margin:6px 0;padding:6px 10px;background:#FFFDF5;border-radius:6px;border-left:3px solid #E87A20}}
.t-bluebook{{font-size:12px;color:#777;margin:6px 0;padding:6px 10px;background:#F8F8FE;border-radius:6px;border-left:3px solid #3E54CE;line-height:1.5}}
.t-stocks{{margin-top:8px}}
.stock-group{{margin:6px 0}}
.stock-group .sg-label{{font-size:11px;font-weight:700;display:inline-block;padding:1px 8px;border-radius:3px;margin-right:6px}}
.sg-label.l1{{background:#FFF0F0;color:#C4433A}}
.sg-label.l2{{background:#FFF3E8;color:#E87A20}}
.sg-label.l3{{background:#EEF0FF;color:#3E54CE}}
.tsr{{display:inline-block;margin:3px 6px;font-size:13px;cursor:default;position:relative}}
.tsr .tsc{{font-weight:600;margin-left:3px}}
.tsr .sn{{color:#1a1a2e;font-weight:600}}
.tsr .sc{{font-size:10px;color:#aaa;margin-left:2px}}
.sec-title{{font-size:18px;font-weight:700;color:#1a1a2e;margin:20px 0 12px;padding-bottom:8px;border-bottom:2px solid #eee}}
.sec-title .star{{color:#FFD700;margin-right:4px}}
.alpha-row{{display:flex;align-items:center;padding:8px 12px;border-bottom:1px solid #f0f0f0;font-size:13px;gap:10px;flex-wrap:wrap}}
.alpha-row.top5{{background:#FFFDF5}}
.ap{{font-weight:600;color:#1a1a2e;min-width:80px}}
.ap .ascore{{display:inline-block;background:#1a1a2e;color:#FFD700;font-size:10px;padding:1px 8px;border-radius:3px;margin-left:4px;font-weight:700}}
.ap .reason{{font-size:12px;color:#666;flex:1;min-width:120px}}
.ap .price-info{{font-size:12px;color:#888;white-space:nowrap}}
.ap .pct{{font-weight:700;margin-left:4px}}
.fo{{text-align:center;padding:20px;font-size:11px;color:#aaa;line-height:1.8}}
.fo a{{color:#3E54CE;text-decoration:none}}
@media(max-width:640px){{
.w{{padding:8px}}
.sh{{padding:16px 12px}}
.sh h1{{font-size:18px}}
.stats{{gap:12px}}
.ct{{padding:12px}}
.alpha-row{{font-size:12px;gap:6px}}
}}
@keyframes flash-green{{0%{{background:#E8F5E9}}100%{{background:transparent}}}}
@keyframes flash-red{{0%{{background:#FFEBEE}}100%{{background:transparent}}}}
.flash-up{{animation:flash-red .8s ease-out}}
.flash-down{{animation:flash-green .8s ease-out}}
</style>
</head>
<body>
<div class="w">
<div class="sh">
<h1>⚡ 蓝宝书<span>Max</span> · 每日机构投研精华</h1>
<div class="sub">机构观点快照 · {edition_info["badge"]}</div>
<div class="badge">{edition_name} · {date_display}</div>
<span class="live-dot"></span><span style="font-size:10px;opacity:.7">实时行情</span>
<div class="stats">
<span>📊 覆盖标的 <b>{total}</b></span>
<span class="up">📈 上涨 <b>{up_count}</b></span>
<span class="down">📉 下跌 <b>{down_count}</b></span>
<span>⏰ 更新 {datetime.now(CST).strftime("%H:%M")}</span>
</div>
</div>
<div class="ct">
<div class="summary-card">
<h3>📋 今日市场摘要</h3>
<div class="summary-one-liner">💡 数据更新中，请稍候刷新页面获取最新蓝宝书内容。当前展示 {edition_name} 标的实时行情。</div>
<div class="summary-meta">
<span>🏷️ {edition_name}</span>
<span>📅 {date_display}</span>
<span>🔒 模板锁定 v1</span>
</div>
</div>

<div class="sec-title"><span class="star">📋</span> 全部标的全景</div>
'''

    # Alpha区 - 全部标的按涨跌幅排序
    sorted_stocks = sorted(
        [(name, STOCK_CODES[name], prices.get(STOCK_CODES[name], {})) for name in STOCK_CODES if STOCK_CODES[name] in prices],
        key=lambda x: x[2].get("pct", 0),
        reverse=True
    )

    for idx, (name, code, info) in enumerate(sorted_stocks, 1):
        pct = info.get("pct", 0)
        price = info.get("price", 0)
        color = "#C4433A" if pct > 0 else ("#3D4826" if pct < 0 else "#888")
        prefix = "+" if pct > 0 else ""
        top5_class = " top5" if idx <= 5 else ""
        html += f'<div class="alpha-row{top5_class}"><span class="ap" data-stock="{name}" data-field="pct"><span class="sn">{name}</span><span class="sc">{code[2:]}</span><span class="pct" style="color:{color}">{prefix}{pct:.2f}%</span></span></div>\n'

    html += f'''
</div>
<div class="fo">
<p>数据来源：Alpha派蓝宝书 · 东方财富实时行情</p>
<p>⚠️ 本页面为机构投研信息聚合参考，非投资建议</p>
<p>🔒 模板版本 v1 · 锁定交付物 am-20260622-live.html</p>
<p>Generated by <a href="https://allyhub.com">AllyHub</a> · 蓝宝书Max</p>
</div>
</div>

<script>
// === 蓝宝书Max · 实时行情引擎 v1 🔒 ===
{secid_map_js}

const PRICE_CACHE = {{}};
let isFetching = false;

async function fetchPrices() {{
  if (isFetching) return;
  isFetching = true;
  const secids = Object.values(SECID_MAP);
  const batchSize = 50;
  const batches = [];
  for (let i = 0; i < secids.length; i += batchSize) {{
    batches.push(secids.slice(i, i + batchSize));
  }}
  for (const batch of batches) {{
    try {{
      const url = `https://push2.eastmoney.com/api/qt/ulist.np/get?secids=${{batch.join(',')}}&fields=f2,f3,f12,f14&fltt=2`;
      const resp = await fetch(url);
      const data = await resp.json();
      if (data && data.data && data.data.diff) {{
        for (const item of data.data.diff) {{
          PRICE_CACHE[item.f14] = {{
            price: (item.f2 || 0) / 100,
            pct: (item.f3 || 0) / 100,
            code: item.f12
          }};
        }}
      }}
    }} catch(e) {{ console.warn('Fetch batch failed:', e); }}
  }}
  updatePrices();
  isFetching = false;
}}

function updatePrices() {{
  const els = document.querySelectorAll('[data-stock]');
  let updated = 0;
  els.forEach(el => {{
    const name = el.getAttribute('data-stock');
    const data = PRICE_CACHE[name];
    if (!data) return;
    let target = el;
    let field = el.getAttribute('data-field');
    if (!field) {{
      const child = el.querySelector('[data-field]');
      if (child) {{ target = child; field = child.getAttribute('data-field'); }}
    }}
    if (!field) return;
    if (field === 'pct') {{
      const oldPct = parseFloat(target.textContent?.replace(/[+%]/g, '') || 0);
      const newPct = data.pct;
      if (Math.abs(newPct - oldPct) > 0.001) {{
        const prefix = newPct > 0 ? '+' : '';
        const color = newPct > 0 ? '#C4433A' : (newPct < 0 ? '#3D4826' : '#888');
        target.textContent = `${{prefix}}${{newPct.toFixed(2)}}%`;
        target.style.color = color;
        target.style.animation = 'none';
        target.offsetHeight;
        target.style.animation = newPct > oldPct ? 'flash-red .8s ease-out' : 'flash-green .8s ease-out';
        updated++;
      }}
    }}
  }});
}}

fetchPrices();
setInterval(fetchPrices, 3000);
</script>
</body>
</html>'''

    return html


def main():
    parser = argparse.ArgumentParser(description="蓝宝书Max 自动生成器 v1")
    parser.add_argument("--edition", required=True, choices=["am","md","pm","gl"],
                        help="版本: am=晨会 md=午间 pm=晚间 gl=全球")
    parser.add_argument("--output-dir", default=".",
                        help="输出目录")
    args = parser.parse_args()

    today = datetime.now(CST).strftime("%Y%m%d")
    edition = args.edition
    edition_name = EDITION_CONFIG[edition]["name"]

    print(f"🚀 蓝宝书Max · {edition_name} 自动生成器 v1")
    print(f"📅 日期: {today}")
    print(f"🔒 模板: am-20260622-live.html 锁定")

    # 1. 获取行情
    print(f"\n📊 正在获取 {len(STOCK_CODES)} 只标的实时行情...")
    prices = get_all_prices(STOCK_CODES)
    print(f"✅ 获取成功: {len(prices)} 只")

    # 2. 生成HTML
    print(f"\n📝 正在生成 {edition_name} HTML...")
    html = generate_html(edition, today, prices)

    # 3. 写入文件
    filename = f"{edition}-{today}.html"
    filepath = os.path.join(args.output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    size_kb = os.path.getsize(filepath) / 1024
    print(f"✅ 已生成: {filename} ({size_kb:.0f} KB)")

    # 4. 打印摘要
    up = sum(1 for p in prices.values() if p["pct"] > 0)
    down = sum(1 for p in prices.values() if p["pct"] < 0)
    print(f"\n📊 行情摘要: {len(prices)}只 | 📈{up}只 | 📉{down}只")
    print(f"✨ {edition_name} 生成完成！")


if __name__ == "__main__":
    main()
