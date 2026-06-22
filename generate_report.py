#!/usr/bin/env python3
"""
蓝宝书Max · 自动化报告生成器 (v5固化版)
用于GitHub Actions定时任务，从Alpha派API获取晨会版数据并生成HTML。
"""
import os, sys, json, re, urllib.request, ssl, hashlib, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ============================================================
# 配置
# ============================================================
CST = timezone(timedelta(hours=8))
AUTH_TOKEN = os.environ.get("ALPHAPAI_TOKEN", "")
VT_TOKEN = os.environ.get("ALPHAPAI_VT_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "")

ALPHAPAI_BASE = "https://alphapai-web.rabyte.cn/external/alpha/api"
TENCENT_API = "http://qt.gtimg.cn/q={codes}"

# ============================================================
# 股票代码映射 (from runbook v5)
# ============================================================
STOCK_CODES = {
    "中瓷电子":"sz003031","国瓷材料":"sz300285","中钨高新":"sz000657",
    "鼎泰高科":"sz301377","生益科技":"sh600183","国际复材":"sz301526",
    "宏和科技":"sz002256","铜冠铜箔":"sz301217","德福科技":"sz301511",
    "光华科技":"sz002741","天承科技":"sh688603",
    "兆易创新":"sh603986","普冉股份":"sh688766","江波龙":"sz301308",
    "香农芯创":"sz300475","佰维存储":"sh688525","国科微":"sz300672",
    "风华高科":"sz000636","三环集团":"sz300408",
    "北方华创":"sz002371","中微公司":"sh688012","盛美上海":"sh688082",
    "拓荆科技":"sh688072","长川科技":"sz300604","华峰测控":"sh688200",
    "富创精密":"sh688409","新莱应材":"sz301187","京仪装备":"sh688115",
    "珂玛科技":"sz301130",
    "中天科技":"sh600522","长飞光纤":"sh601869","亨通光电":"sh600487",
    "太辰光":"sz300570","永鼎股份":"sh600105","烽火通信":"sh600498",
    "海光信息":"sh688041","寒武纪":"sh688256","中科曙光":"sh603019",
    "润建股份":"sz002929","亚康股份":"sz301085",
    "洁美科技":"sz002859","商络电子":"sz300975","雅创电子":"sz003015",
    "帝尔激光":"sz300776","芯碁微装":"sh688630","德龙激光":"sh688170",
    "东威科技":"sh688700","沃格光电":"sz300747","京东方A":"sz000725",
    "凯盛科技":"sh600552","戈碧迦":"bj835438","鼎龙股份":"sz300054",
    "爱迪特":"sz300896","三祥新材":"sh603663","盛和资源":"sh600392",
    "金博股份":"sh688598","东方锆业":"sz002167",
    "中国中免":"sh601888","长白山":"sh603099","峨眉山A":"sz000888",
    "宋城演艺":"sz301025","黄山旅游":"sh600054","锦江酒店":"sh600754",
    "保利发展":"sh600048","滨江集团":"sz002244","我爱我家":"sz000560",
    "中国国贸":"sh600007","张江高科":"sh600895",
    "弘信电子":"sz300657","软通动力":"sz301236","宏景科技":"sz301396",
    "协创数据":"sz300857","润泽科技":"sz300442",
    "浙江荣泰":"sh603119","恒立液压":"sh601100","斯菱智驱":"sz301550",
    "恒帅股份":"sz300969","宁波华翔":"sz002048","福赛科技":"sz301529",
    "岱美股份":"sh603730","日盈电子":"sh603286",
    "扬杰科技":"sz300373","新洁能":"sh605111","华润微":"sh688396",
    "士兰微":"sh600460","捷捷微电":"sz300623","斯达半导":"sh603290",
    "上海瀚讯":"sz300762","信科移动":"sh688387","信维通信":"sz300136",
    "通宇通讯":"sz002792","臻镭科技":"sh688270","铖昌科技":"sz300782",
    "华测导航":"sz300627",
    "申菱环境":"sz301018","英维克":"sz002837","飞龙股份":"sz002536",
    "领益智造":"sz002600","大元泵业":"sh603757","奕东电子":"sz301123",
    "鼎通科技":"sh688668","川润股份":"sz002272",
    "恒瑞医药":"sh600276","三生国健":"sh688336",
    "星源材质":"sz300568","宁德时代":"sz300750","恩捷股份":"sz002812",
    "佛塑科技":"sz000973",
    "中信证券":"sh600030","华泰证券":"sh601688",
    "中国人寿":"sh601628","中国平安":"sh601318",
    "兴业科技":"sz002468","厦门钨业":"sh600549","章源钨业":"sz002378",
    "中船特气":"sh688146",
}

# ============================================================
# API 工具函数
# ============================================================
def api_get(url, timeout=30):
    """调用Alpha派API"""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url)
    if AUTH_TOKEN:
        req.add_header("Authorization", f"Bearer {AUTH_TOKEN}")
    if VT_TOKEN:
        req.add_header("vt-token", VT_TOKEN)
    req.add_header("User-Agent", "Mozilla/5.0 BluebookMax/5.0")
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return json.loads(resp.read().decode())

def fetch_latest_morning_report():
    """获取最新晨会版报告"""
    url = f"{ALPHAPAI_BASE}/mix/hot/topic/report/list/v2?pageNum=1&pageSize=10&id=&word=&isUs=false&marketType="
    data = api_get(url)
    items = data.get("data", {}).get("data", [])
    for item in items:
        if item.get("batchName") == "晨报" and item.get("marketType") == 21:
            return item
    return None

def fetch_report_detail(report_id):
    """获取报告详情"""
    url = f"{ALPHAPAI_BASE}/mix/hot/topic/report/detail/v2?id={report_id}&isUs=false"
    data = api_get(url)
    return data.get("data", {})

def fetch_stock_prices(codes_list):
    """批量获取腾讯行情"""
    if not codes_list:
        return {}
    # Batch by 50
    all_prices = {}
    for i in range(0, len(codes_list), 50):
        batch = codes_list[i:i+50]
        codes_str = ",".join(batch)
        url = TENCENT_API.format(codes=codes_str)
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                raw = resp.read().decode("gbk", errors="replace")
                for line in raw.strip().split("\n"):
                    if "~" not in line:
                        continue
                    parts = line.split("~")
                    if len(parts) < 5:
                        continue
                    code = parts[2]
                    name = parts[1]
                    try:
                        price = float(parts[3]) if parts[3] else 0
                        prev_close = float(parts[4]) if parts[4] else 0
                    except ValueError:
                        continue
                    change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0
                    all_prices[code] = {
                        "name": name,
                        "price": price,
                        "prevClose": prev_close,
                        "changePct": round(change_pct, 2)
                    }
        except Exception as e:
            print(f"  ⚠ 行情获取失败: {e}")
    return all_prices

# ============================================================
# 评分引擎
# ============================================================
PHASE_MAP = {
    "主升": {"label": "🔥主升", "color": "#C4433A", "min_score": 75},
    "强化": {"label": "📈强化", "color": "#E87A20", "min_score": 55},
    "持续": {"label": "➡️持续", "color": "#3E54CE", "min_score": 35},
    "孵化": {"label": "🌱孵化", "color": "#8B5CF6", "min_score": 0},
}

def determine_phase(score):
    if score >= 75: return "主升"
    if score >= 55: return "强化"
    if score >= 35: return "持续"
    return "孵化"

def calculate_topic_heat(index, summary_text=""):
    """计算主题热度指数 (0-100)"""
    # 机构关注度: based on rank (TOP1 = 50, decreasing)
    attention = max(10, 50 - (index - 1) * 2)
    # 市场确认度: from summary context (default mid-range)
    confirmation = 15 + (index < 5) * 5 + (index < 3) * 5
    # 催化质量: from content hints
    catalyst = 12 + (index < 4) * 5 + (index < 8) * 3
    total = attention + confirmation + catalyst
    return {
        "total": min(99, max(10, total)),
        "attention": attention,
        "confirmation": confirmation,
        "catalyst": catalyst
    }

def calculate_alpha_score(stock, topic_index, topic_heat, category, change_pct=0):
    """计算Alpha评分"""
    # 催化质量 0-30
    if category == "l1" and topic_index <= 3:
        catalyst = 26 if topic_index <= 3 else 22
    elif category == "l1":
        catalyst = 22
    elif category == "l2" and topic_index <= 3:
        catalyst = 20
    elif category == "l2":
        catalyst = 16
    else:
        catalyst = 12
    
    # 主题热度 0-25
    heat_score = min(25, max(5, 26 - topic_index))
    
    # 产业地位 0-25
    if category == "l1":
        position = 22
    elif category == "l2":
        position = 15
    else:
        position = 10
    
    # 市场确认 0-20
    if change_pct >= 10: market = 18
    elif change_pct >= 5: market = 14
    elif change_pct >= 2: market = 10
    elif change_pct >= 0: market = 8
    elif change_pct >= -3: market = 5
    else: market = 3
    
    return catalyst + heat_score + position + market

# ============================================================
# HTML 生成
# ============================================================
def get_css():
    """返回v8固化CSS"""
    return '''    :root{--bg:#E4E1DC;--card:#FDFCF9;--up:#C4433A;--dn:#3D4826;--b1:#C4433A15;--b2:#E87A2015;--b3:#3E54CE15;--b4:#8B5CF615;--tx:#2C2C2C;--tx2:#5C5C5C;--brdr:#E8E6E2;--shd:0 1px 3px rgba(0,0,0,.04)}
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--tx);line-height:1.6;-webkit-font-smoothing:antialiased}
    .w{max-width:860px;margin:0 auto;padding:0 16px}
    .sh{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);color:#fff;padding:28px 24px;border-radius:0 0 16px 16px;text-align:center}
    .sd{font-size:20px;font-weight:700;letter-spacing:2px}
    .sh1{font-size:13px;opacity:.9;margin-top:6px}
    .vb{display:inline-block;padding:2px 10px;border-radius:10px;font-size:11px;margin-left:6px;font-weight:600;vertical-align:middle}
    .vb.dom{background:#EDE4DC;color:#8B6914}
    .vb.gl{background:#DEE5F7;color:#2A4B9A}
    .sm{display:flex;gap:16px;justify-content:center;margin-top:14px;flex-wrap:wrap}
    .smi{background:rgba(255,255,255,.12);padding:6px 16px;border-radius:20px;font-size:13px}
    .smi strong{font-size:18px;color:#FFD700}
    .ct{padding-top:18px}
    .sc{background:var(--card);border:1px solid var(--brdr);border-radius:12px;padding:18px 20px;margin-bottom:16px;box-shadow:var(--shd)}
    .st{font-size:14px;font-weight:600;color:var(--tx);margin-bottom:8px}
    .sm2{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px;font-size:12px;color:var(--tx2)}
    .chg{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
    .tag-s{background:#C4433A10;color:#C4433A;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600}
    .tag-d{background:#3D482610;color:#3D4826;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600}
    .s2{font-size:15px;font-weight:700;color:var(--tx);margin:20px 0 10px;padding-left:8px;border-left:3px solid #C4433A}
    .grid{display:grid;gap:10px;margin-bottom:16px}
    .tc{background:var(--card);border:1px solid var(--brdr);border-radius:10px;padding:14px 16px;box-shadow:var(--shd);transition:box-shadow .2s}
    .tc:hover{box-shadow:0 2px 12px rgba(0,0,0,.08)}
    .th{display:flex;align-items:center;gap:8px;flex-wrap:wrap;position:relative}
    .tr{background:#C4433A;color:#fff;font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;flex-shrink:0}
    .tn{font-size:15px;font-weight:700;color:var(--tx)}
    .sb{font-size:11px;padding:2px 8px;border-radius:8px;font-weight:600;flex-shrink:0}
    .ts{display:inline-flex;align-items:center;gap:4px;margin-left:auto;position:relative;cursor:default}
    .tsv{font-size:20px;font-weight:800}
    .hib{font-size:11px;color:#999;cursor:pointer;user-select:none}
    .hib:hover{color:#555}
    .hp{display:none;position:absolute;top:100%;right:0;background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:10px 14px;box-shadow:0 4px 16px rgba(0,0,0,.12);z-index:100;min-width:220px;white-space:nowrap}
    .pt{font-size:12px;font-weight:600;color:#333;margin-bottom:4px}
    .pb{font-size:11px;color:#666}
    .tr2,.tbb{font-size:13px;color:var(--tx2);line-height:1.7;margin-top:8px;padding-left:4px}
    .tbb{color:#5C5C5C;font-style:italic;border-left:2px solid #3E54CE20;padding-left:10px}
    .tsl{margin-top:10px}
    .t-sg{margin-bottom:6px}
    .t-gl{font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;display:inline-block;margin-bottom:4px}
    .t-gl.l1{background:#C4433A15;color:#C4433A}
    .t-gl.l2{background:#E87A2015;color:#E87A20}
    .t-gl.l3{background:#3E54CE10;color:#3E54CE}
    .tsr{display:flex;align-items:center;gap:8px;padding:4px 8px;font-size:13px;border-radius:6px;flex-wrap:wrap}
    .tsr:hover{background:#F8F7F5}
    .tsn{font-weight:600;color:var(--tx);min-width:60px}
    .tcd{font-size:10px;color:#aaa;min-width:42px}
    .tsc{font-weight:700;font-size:13px;min-width:52px;text-align:right}
    .tsc.up{color:var(--up)}
    .tsc.dn{color:var(--dn)}
    .tsr2{font-size:12px;color:var(--tx2);flex:1}
    .alpha-list{margin-bottom:20px}
    .asc{display:flex;align-items:center;gap:10px;padding:8px 12px;border-bottom:1px solid #f0ede8;font-size:13px}
    .asc:hover{background:#F8F7F5}
    .ar{font-size:16px;font-weight:700;min-width:20px;text-align:center}
    .ar.ldr{color:#DAA520}
    .ai{flex:1;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
    .an{font-weight:600;color:var(--tx)}
    .ab{background:#F5F4F2;color:#5C5C5C;font-size:11px;padding:2px 8px;border-radius:4px;font-weight:600}
    .ar2{font-size:12px;color:var(--tx2);flex:1}
    .ap{font-weight:700;font-size:13px;min-width:52px;text-align:right}
    .ap.up{color:var(--up)}
    .ap.dn{color:var(--dn)}
    .fo{text-align:center;padding:30px 16px;font-size:11px;color:#999;border-top:1px solid #e0ded8;margin-top:20px}
    .tc.opp{border-left:3px solid #9B59B6}
    @media (max-width:640px){
      .w{padding:0 8px}
      .sh{padding:20px 16px}
      .sd{font-size:16px}
      .sm{gap:8px}
      .smi{font-size:11px;padding:4px 12px}
      .smi strong{font-size:16px}
      .tc{padding:12px}
      .tn{font-size:14px}
      .tsv{font-size:17px}
      .th{gap:4px}
      .tsr{font-size:12px;gap:4px}
      .tsn{min-width:48px;font-size:12px}
      .tsc{min-width:44px;font-size:12px}
      .tsr2{font-size:10px}
    }'''

def render_topic_card(topic, index, is_opportunity=False, prices=None):
    """渲染单个主题卡片HTML"""
    topic_name = topic.get("topicName", "")
    summary = topic.get("summary", "")
    
    # 分解summary为 📌 和 📘 两部分
    parts = summary.split("<br><br>")
    event_summary = parts[0] if parts else summary
    # 去除 "关注：**股票名**..." 后面的关注部分，只保留事件描述
    event_summary = re.sub(r'关注：.*$', '', event_summary, flags=re.DOTALL).strip()
    event_summary = re.sub(r'<br>.*$', '', event_summary).strip()
    event_summary = event_summary.replace("<br>", " ").strip()
    
    bluebook_quote = ""
    if len(parts) > 1:
        bluebook_quote = parts[1]
        # 同样去除关注部分
        bluebook_quote = re.sub(r'关注：.*$', '', bluebook_quote, flags=re.DOTALL).strip()
        # 去除 "，关注" 之后的内容
        bluebook_quote = re.sub(r'，关注.*$', '', bluebook_quote).strip()
    else:
        # 从单段文字中提取不同角度
        bluebook_quote = summary[:200] + ("..." if len(summary) > 200 else "")
    
    # 计算热度
    heat = calculate_topic_heat(index + 1, summary)
    phase = determine_phase(heat["total"])
    phase_info = PHASE_MAP[phase]
    
    score_color = phase_info["color"]
    if heat["total"] >= 60:
        score_color = "#C4433A"
    elif heat["total"] >= 40:
        score_color = "#E87A20"
    elif heat["total"] >= 25:
        score_color = "#3E54CE"
    else:
        score_color = "#8B5CF6"
    
    popup_id = f"popup_{'opp_' if is_opportunity else ''}{index}"
    
    # 解析股票
    stocks = parse_stocks_from_summary(summary, topic_name)
    
    # 构建股票行HTML
    def render_stock_group(category, stock_list):
        if not stock_list:
            return ""
        labels = {"l1": "龙头首选", "l2": "弹性机会", "l3": "相关标的"}
        rows = []
        for s in stock_list:
            name = s["name"]
            code = STOCK_CODES.get(name, "")
            short_code = code[2:] if code else ""
            price_info = prices.get(code, {}) if code else {}
            change = price_info.get("changePct", 0)
            change_str = f"{change:+.2f}%" if change else "--"
            css_class = "up" if change > 0 else ("dn" if change < 0 else "")
            reason = s.get("reason", "蓝宝书推荐")
            rows.append(f'<div class="tsr"><span class="tsn">{name}</span><span class="tcd">{short_code}</span><span class="tsc {css_class}">{change_str}</span><span class="tsr2">{reason}</span></div>')
        return f'<div class="t-sg"><div class="t-gl {category}">{labels[category]}</div>{"".join(rows)}</div>'
    
    l1_html = render_stock_group("l1", stocks["l1"])
    l2_html = render_stock_group("l2", stocks["l2"])
    l3_html = render_stock_group("l3", stocks["l3"])
    
    # 完整卡片
    border_style = 'border-left:3px solid #9B59B6' if is_opportunity else ''
    name_style = 'font-size:16px' if is_opportunity else ''
    
    top_badge = f'<span class="tr">TOP{index+1}</span>' if not is_opportunity else ''
    
    html = f'''    <div class="tc{" opp" if is_opportunity else ""}" style="{border_style}">
    <div class="th">{top_badge}<span class="tn" style="{name_style}">{topic_name}</span><span class="sb" style="background:{phase_info['color']}15;color:{phase_info['color']}">{phase_info['label']}</span><span class="ts"><span class="tsv" style="color:{score_color}">{heat['total']}</span><span class="hib" data-popup="{popup_id}" onclick="event.stopPropagation();var p=document.getElementById('{popup_id}');p.style.display=p.style.display==='block'?'none':'block';">ⓘ</span><div class="hp" id="{popup_id}"><div class="pt">{topic_name} · 热度指数构成</div><div class="pb">机构关注度 {heat['attention']} | 市场确认度 {heat['confirmation']} | 催化质量 {heat['catalyst']}</div></div></span></div>
    <div class="tr2">📌 {event_summary}</div>
    <div class="tbb">📘 {bluebook_quote}</div>
    <div class="tsl">{l1_html}{l2_html}{l3_html}</div></div>'''
    
    return html

def parse_stocks_from_summary(summary, topic_name):
    """从蓝宝书摘要中解析股票分组"""
    result = {"l1": [], "l2": [], "l3": []}
    
    # 提取关注部分
    focus_match = re.search(r'关注[：:](.*?)$', summary, re.DOTALL)
    if not focus_match:
        return result
    
    focus_text = focus_match.group(1)
    
    # 按 /**/ 分隔股票组
    groups = re.split(r'\*\*/|/\*\*', focus_text)
    
    current_category = "l3"
    for segment in groups:
        segment = segment.strip()
        if not segment:
            continue
        
        # 检测龙头/弹性标记
        if "龙头" in segment or "首选" in segment:
            current_category = "l1"
        elif "弹性" in segment:
            current_category = "l2"
        
        # 提取股票名（**股票名** 格式）
        stocks = re.findall(r'\*\*([^*]+)\*\*', segment)
        for stock in stocks:
            stock = stock.strip()
            if stock and stock in STOCK_CODES:
                # 提取理由
                reason_match = re.search(rf'\*\*{re.escape(stock)}\*\*[^，。,.]*[，。,.]?\s*([^，。]*[受益|龙头|核心|弹性|直接|深度|供应|切入].*?)(?=\*\*|，|。|$)', segment)
                reason = reason_match.group(1).strip() if reason_match else "蓝宝书推荐"
                result[current_category].append({"name": stock, "reason": reason})
    
    return result

def render_alpha_row(stock, rank, is_top5, change_pct_str):
    """渲染Alpha行"""
    star = "★" if is_top5 else "·"
    star_class = "ldr" if is_top5 else ""
    css_class = "up" if stock["changePct"] > 0 else ("dn" if stock["changePct"] < 0 else "")
    name = stock["name"]
    code = STOCK_CODES.get(name, "")
    short_code = code[2:] if code else ""
    score = stock.get("score", 0)
    reason = stock.get("reason", "蓝宝书推荐")
    
    return f'<div class="asc"><span class="ar {star_class}">{star}</span><div class="ai"><span class="an">{name}</span><span class="tcd" style="font-size:11px;color:#999">{short_code}</span><span class="ab">{score}</span><span class="ar2">{reason}</span></div><div class="ap {css_class}">{change_pct_str}</div></div>'

def generate_html(report_detail, prices, edition_type="am"):
    """生成完整HTML"""
    now = datetime.now(CST)
    date_str = report_detail.get("date", now.strftime("%Y-%m-%d"))
    title = report_detail.get("title", f"{date_str} 晨会版")
    
    # 解析日期
    try:
        report_date = datetime.strptime(date_str, "%Y-%m-%d")
    except:
        report_date = now
    date_display = report_date.strftime("%Y年%-m月%-d日")
    
    # 版本名
    if edition_type == "am":
        version_name = "晨会版"
        version_emoji = "🌅"
    elif edition_type == "pm":
        version_name = "晚间版"
        version_emoji = "🌙"
    elif edition_type == "md":
        version_name = "午间版"
        version_emoji = "☀️"
    elif edition_type == "gl":
        version_name = "全球版"
        version_emoji = "🌍"
    else:
        version_name = "晨会版"
        version_emoji = "🌅"
    
    # 解析主题
    content_json = report_detail.get("contentJson", [])
    topics = []
    opportunities = []
    
    if isinstance(content_json, list):
        for section in content_json:
            if isinstance(section, dict):
                children = section.get("children", [])
                for child in children:
                    if isinstance(child, dict):
                        child_index = child.get("index", 10)
                        if child_index >= 8:
                            opportunities.append(child)
                        else:
                            topics.append(child)
    
    # 按index排序
    topics.sort(key=lambda x: x.get("index", 99))
    opportunities.sort(key=lambda x: x.get("index", 99))
    
    num_topics = len(topics)
    num_opp = len(opportunities)
    
    # 收集所有股票代码
    all_codes = set()
    for t in topics + opportunities:
        summary = t.get("summary", "")
        for name, code in STOCK_CODES.items():
            if name in summary:
                all_codes.add(code)
    
    # 获取行情
    if prices is None:
        prices = fetch_stock_prices(list(all_codes))
    
    # 统计涨跌
    up_count = sum(1 for p in prices.values() if p.get("changePct", 0) > 0)
    dn_count = sum(1 for p in prices.values() if p.get("changePct", 0) < 0)
    total_stocks = len(prices)
    
    # 今日摘要
    top3 = topics[:3]
    top3_text = " · ".join([f"【{t.get('topicName','')}】热度{calculate_topic_heat(i+1)['total']}" for i, t in enumerate(top3)])
    
    # 生成主题卡片
    topic_cards = []
    for i, t in enumerate(topics):
        topic_cards.append(render_topic_card(t, i, is_opportunity=False, prices=prices))
    
    # 生成机会卡片
    opp_cards = []
    for i, t in enumerate(opportunities):
        opp_cards.append(render_topic_card(t, i, is_opportunity=True, prices=prices))
    
    # 生成Alpha
    alpha_stocks = []
    seen = set()
    for i, t in enumerate(topics + opportunities):
        summary = t.get("summary", "")
        stocks_data = parse_stocks_from_summary(summary, t.get("topicName", ""))
        for cat in ["l1", "l2", "l3"]:
            for s in stocks_data[cat]:
                name = s["name"]
                if name in seen:
                    continue
                seen.add(name)
                code = STOCK_CODES.get(name, "")
                price_info = prices.get(code, {})
                change_pct = price_info.get("changePct", 0)
                score = calculate_alpha_score(s, i+1, 0, cat, change_pct)
                alpha_stocks.append({
                    "name": name, "score": score, "changePct": change_pct,
                    "reason": s.get("reason", ""), "topic": t.get("topicName", "")
                })
    
    alpha_stocks.sort(key=lambda x: x["score"], reverse=True)
    
    top5 = alpha_stocks[:5]
    rest = alpha_stocks[5:]
    
    top5_html = "\n".join([render_alpha_row(s, i, True, f"{s['changePct']:+.2f}%") for i, s in enumerate(top5)])
    rest_html = "\n".join([render_alpha_row(s, i, False, f"{s['changePct']:+.2f}%") for i, s in enumerate(rest)])
    
    # 拼装完整HTML
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>蓝宝书Max · {date_display} {version_name}</title>
<style>{get_css()}</style></head>
<body>
<div class="w">
<div class="sh"><div class="sd">⚡ 蓝宝书Max · 每日机构投研精华</div>
<div class="sh1">机构观点快照<span class="vb dom">国内版 🧡</span></div>
<div style="font-size:13px;color:rgba(255,255,255,.85);margin-top:4px;font-weight:500">📋 {date_display} {version_name} · {num_topics}主题 · 覆盖沪深A股</div>
<div class="sm"><div class="smi"><strong>{num_topics}</strong> 全部主题</div><div class="smi"><strong>{num_opp}</strong> 机会前瞻</div><div class="smi"><strong>{total_stocks}</strong> 推荐标的</div></div></div>
<div class="ct">
    <div class="sc">
    <div style="font-size:12px;font-weight:700;color:#C47A00;margin-bottom:4px">📋 今日市场摘要</div>
    <div class="st">最强方向：{top3_text}</div>
    <div class="sm2"><div class="smi2"><strong>{num_topics}</strong> 全部主题 · <strong>{num_opp}</strong> 机会前瞻 · <strong>{total_stocks}</strong> 推荐标的 · {up_count}涨{dn_count}跌</div></div>
    <div class="chg">{''.join([f'<span class="tag-s">↑ {t.get("topicName","")}</span>' for t in topics[:5]])}</div>
    </div>
    <div class="s2">🔥 全部主题 ({num_topics}个)<span style="font-size:11px;font-weight:400;color:#999;margin-left:6px">按热度排序 · 点击ⓘ查看三维度评分</span></div>
    <div class="grid">
{"".join(topic_cards)}
    </div>
    <div class="s2" style="margin-top:4px">🔮 机会前瞻 <span style="font-size:11px;font-weight:400;color:#999;margin-left:6px">机构新增关注、逐渐发酵的新话题</span></div>
    <div class="grid" style="margin-bottom:20px">
{"".join(opp_cards)}
    </div>
    <div class="s2" style="margin-top:20px">★ 今日Top5 Alpha<span style="font-size:10px;font-weight:400;color:#999;background:#F5F4F2;padding:3px 8px;border-radius:4px;margin-left:6px">综合催化质量·主题热度·产业地位·市场确认</span></div>
    <div class="alpha-list">
{top5_html}
    </div>
    <div class="s2" style="border-left-color:#3E54CE">📋 全部Alpha<span style="font-size:10px;font-weight:400;color:#999;background:#F5F4F2;padding:3px 8px;border-radius:4px;margin-left:6px">覆盖全部主题标的 · 去重排序</span></div>
    <div class="alpha-list">
{rest_html}
    </div>
</div>
<div class="fo">
蓝宝书Max v5 固化版 · 数据来源：Alpha派蓝宝书 · 行情：腾讯API · 报告基于机构投研信息聚合，非投资建议<br>
{date_display} {version_name} · Auto-generated by Ally · {now.strftime("%H:%M")} CST
</div>
</div>
<script>
document.addEventListener('click',function(e){{if(!e.target.closest('.hib')){{var pops=document.querySelectorAll('.hp');for(var i=0;i<pops.length;i++)pops[i].style.display='none';}}}});
</script>
</body></html>'''
    
    return html

# ============================================================
# 主函数
# ============================================================
def main():
    global AUTH_TOKEN, VT_TOKEN
    AUTH_TOKEN = os.environ.get("ALPHAPAI_TOKEN", "")
    VT_TOKEN = os.environ.get("ALPHAPAI_VT_TOKEN", "")
    
    if not AUTH_TOKEN:
        print("❌ ALPHAPAI_TOKEN not set")
        sys.exit(1)
    
    print("🔍 获取最新晨会版报告...")
    report = fetch_latest_morning_report()
    if not report:
        print("❌ 未找到晨会版报告")
        sys.exit(1)
    
    report_id = report["id"]
    title = report["title"]
    date_str = report.get("date", "")
    print(f"  ✓ {title} (id={report_id[:30]}...)")
    
    print("📥 获取报告详情...")
    detail = fetch_report_detail(report_id)
    print(f"  ✓ 获取成功")
    
    print("📊 获取股票行情...")
    content_json = detail.get("contentJson", [])
    all_codes = set()
    if isinstance(content_json, list):
        for section in content_json:
            if isinstance(section, dict):
                for child in section.get("children", []):
                    summary = child.get("summary", "")
                    for name in STOCK_CODES:
                        if name in summary:
                            all_codes.add(STOCK_CODES[name])
    
    prices = fetch_stock_prices(list(all_codes))
    print(f"  ✓ 获取 {len(prices)} 只股票行情")
    
    print("📝 生成HTML...")
    html = generate_html(detail, prices, edition_type="am")
    
    # 输出文件名
    today = datetime.now(CST).strftime("%Y%m%d")
    output_path = Path("/out/deliverables") / f"am-{today}.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✅ 生成完成: {output_path}")
    print(f"   HTML大小: {len(html):,} chars")
    
    return {
        "outputFile": str(output_path),
        "htmlSize": len(html),
        "title": title,
        "date": date_str,
        "numTopics": len([c for s in (content_json if isinstance(content_json, list) else []) for c in (s.get("children",[]) if isinstance(s, dict) else [])]),
        "numPrices": len(prices)
    }

if __name__ == "__main__":
    main()
