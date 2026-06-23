#!/usr/bin/env python3
"""
蓝宝书Max v3 渲染引擎
从结构化数据生成 deliverable-style 报告 HTML
完全数据驱动，零硬编码
"""
import json
from typing import Dict, List, Optional, Any


# ============================================================
# CSS 模板 —— 与 deliverables_am-20260622-live.html 完全一致
# ============================================================
REPORT_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter Tight',-apple-system,sans-serif;background:#E4E1DC;color:#151515;padding:24px}
.w{max-width:1200px;margin:0 auto;background:#FDFCF9;border-radius:24px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.06)}
.sh{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);color:#fff;padding:28px 36px}
.sd{font-size:11px;font-weight:500;color:rgba(255,255,255,.5)}
.sh1{font-size:28px;font-weight:700;margin-bottom:6px;display:flex;align-items:center;gap:10px}
.vb{font-size:11px;padding:3px 10px;border-radius:20px;font-weight:600}
.vb.dom{background:#EDE4DC;color:#A07858}
.live-dot{display:inline-block;width:8px;height:8px;background:#00E676;border-radius:50%;margin-left:8px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.live-text{font-size:10px;color:rgba(255,255,255,.6);margin-left:6px}
.sm{display:flex;gap:20px;margin-top:16px;flex-wrap:wrap}
.smi{font-size:12px;color:rgba(255,255,255,.6);background:rgba(255,255,255,.06);padding:8px 14px;border-radius:8px;text-align:center;min-width:100px}
.smi strong{color:#fff;font-size:20px;display:block;margin-bottom:2px}
.ct{padding:20px 36px 28px}
.sc{background:#FFF8F0;border:1px solid #FFE8CC;border-radius:10px;padding:14px 18px;margin-bottom:16px}
.st{font-size:14px;line-height:1.5;font-weight:600}
.sm2{display:flex;gap:14px;margin-top:8px;flex-wrap:wrap}
.smi2{font-size:11px;color:#666}
.smi2 strong{color:#151515}
.chg{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.tag-s{font-size:10px;padding:2px 7px;border-radius:3px;font-weight:600;background:#FFE8E8;color:#C4433A}
.tag-n{font-size:10px;padding:2px 7px;border-radius:3px;font-weight:600;background:#E8EEFF;color:#3E54CE}
.s2{font-size:16px;font-weight:700;margin-bottom:10px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:1fr;gap:12px;margin-bottom:20px}
.tc{background:#fff;border:1px solid #E8E6E2;border-radius:10px;padding:14px 18px;position:relative}
.th{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap}
.tr{font-size:10px;font-weight:700;color:#fff;background:#151515;border-radius:3px;padding:2px 6px}
.tn{font-size:20px;font-weight:700;letter-spacing:-0.3px}
.tcd{font-size:10px;color:#aaa;margin:0 4px;font-weight:400}
.ts{margin-left:auto;display:flex;align-items:center;gap:2px;position:relative}
.tsv{font-size:26px;font-weight:700;line-height:1}
.hib{font-size:12px;cursor:pointer;color:#999;display:inline-block;width:16px;height:16px;line-height:16px;text-align:center;border-radius:50%;background:#F0F0F0;font-style:normal}
.hib:hover{background:#E0E0E0;color:#666}
.hp{display:none;position:absolute;top:calc(100% + 4px);right:0;z-index:1000;background:#fff;border:1px solid #E0DDD8;border-radius:8px;padding:12px 16px;min-width:220px;box-shadow:0 4px 16px rgba(0,0,0,.12)}
.pt{font-size:12px;font-weight:700;color:#151515;margin-bottom:4px}
.pb{font-size:11px;color:#888}
.sb{font-size:10px;font-weight:600;padding:2px 7px;border-radius:3px}
.tr2{font-size:13px;color:#151515;font-weight:500;margin-bottom:6px;line-height:1.5}
.tbb{font-size:12px;color:#888;background:#F8F6F3;padding:8px 12px;border-radius:6px;line-height:1.5;border-left:3px solid #D4C8BC;margin-bottom:10px}
.tsl{display:flex;flex-direction:column;gap:6px}
.t-sg{margin-bottom:4px}
.t-gl{font-size:10px;font-weight:600;padding:2px 6px;border-radius:3px;display:inline-block;margin-bottom:3px}
.t-gl.l1{background:#C4433A12;color:#C4433A}
.t-gl.l2{background:#E87A2012;color:#E87A20}
.t-gl.l3{background:#3E54CE12;color:#3E54CE}
.tsr{display:flex;align-items:center;gap:6px;padding:4px 0;border-bottom:1px solid #F5F4F2;font-size:12px;flex-wrap:wrap;transition:background .3s}
.tsr:last-child{border-bottom:none}
.tsn{font-weight:700;font-size:13px;color:#151515;min-width:56px}
.tsc{font-weight:700;font-size:13px;min-width:54px;text-align:right;transition:color .3s}
.tsr2{font-size:11px;color:#999;margin-left:6px;flex:1;min-width:80px}
.up{color:#C4433A}.dn{color:#3D4826}
.asc{display:flex;align-items:center;gap:10px;padding:8px 12px;background:#fff;border:1px solid #E8E6E2;border-radius:8px;margin-bottom:5px;min-height:48px}
.ar{font-size:11px;font-weight:700;color:#C0C0C0;min-width:16px;text-align:center}
.ar.ldr{color:#E8A500;font-size:14px}
.ai{flex:1;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.an{font-size:14px;font-weight:700}
.ab{font-size:10px;font-weight:700;color:#fff;background:#151515;border-radius:3px;padding:1px 5px;text-align:center;line-height:1.4}
.ar2{font-size:11px;color:#A07858;flex:1;min-width:60px}
.ap{font-size:12px;font-weight:600;min-width:55px;text-align:right;white-space:nowrap;transition:color .3s}
.alpha-list{}
.fo{padding:14px 36px;font-size:11px;color:#999;border-top:1px solid #E8E6E2;line-height:1.6}
.fl{margin-top:6px;padding-top:6px;border-top:1px solid #F0EFEC;font-size:10px;color:#B0B0B0}
@media(max-width:600px){
    body{padding:0}.w{border-radius:0}.sh{padding:20px}.ct{padding:16px}.fo{padding:12px 16px}
    .tn{font-size:17px}.tsv{font-size:22px}.th{gap:6px 8px}
    .ts{margin-left:0;width:100%;justify-content:flex-end;margin-top:4px}
    .tr{font-size:9px;padding:2px 5px}.sb{font-size:9px;padding:2px 5px}
}
"""


# ============================================================
# 实时行情 JS 模板
# ============================================================
def render_live_js(secid_map: Dict[str, str]) -> str:
    """生成实时行情 JavaScript（内嵌到 HTML 中）"""
    secid_json = json.dumps(secid_map, ensure_ascii=False)
    return f"""<script>
    // === REAL-TIME STOCK PRICE UPDATER ===
    const SECID_MAP = {secid_json};
    const API_URL = 'https://push2.eastmoney.com/api/qt/ulist.np/get';
    const REFRESH_INTERVAL = 3000;

    let lastPrices = {{}};
    let updateCount = 0;

    const allSecids = [...new Set(Object.values(SECID_MAP))];
    console.log('[Live] Tracking ' + allSecids.length + ' stocks');

    async function fetchPrices() {{
        const batchSize = 50;
        const allData = [];
        for (let i = 0; i < allSecids.length; i += batchSize) {{
            const batch = allSecids.slice(i, i + batchSize);
            const url = API_URL + '?secids=' + batch.join(',') + '&fields=f2,f3,f12,f14&_=' + Date.now();
            try {{
                const resp = await fetch(url);
                const json = await resp.json();
                if (json.data && json.data.diff) allData.push(...json.data.diff);
            }} catch(e) {{ console.warn('[Live] Batch fetch error:', e.message); }}
        }}
        return allData;
    }}

    function updatePrices(data) {{
        const priceMap = {{}};
        for (const item of data) {{
            priceMap[item.f14] = {{ price: item.f2 / 100, pct: item.f3 / 100 }};
        }}

        let changes = 0;
        document.querySelectorAll('[data-stock]').forEach(el => {{
            const name = el.getAttribute('data-stock');
            let field = el.getAttribute('data-field');
            const d = priceMap[name];
            if (!d) return;

            let target = el;
            if (!field) {{
                const child = el.querySelector('[data-field]');
                if (child) {{ target = child; field = child.getAttribute('data-field'); }}
                else return;
            }}

            const newPct = d.pct;
            const oldPct = lastPrices[name];

            if (field === 'pct') {{
                const pctStr = (newPct >= 0 ? '+' : '') + newPct.toFixed(2) + '%';
                if (target.textContent.trim() !== pctStr) {{
                    target.textContent = pctStr;
                    target.className = target.className.replace(/\\bup\\b|\\bdn\\b/g, '').trim()
                        + ' ' + (newPct >= 0 ? 'up' : 'dn');

                    if (oldPct !== undefined && oldPct !== newPct) {{
                        const row = target.closest('.tsr, .asc');
                        if (row) {{
                            row.style.transition = 'background 0.15s';
                            row.style.background = newPct > oldPct ? '#C4433A18' : '#3D482618';
                            setTimeout(() => {{ row.style.background = ''; }}, 900);
                        }}
                        changes++;
                    }}
                }}
            }}
            lastPrices[name] = newPct;
        }});

        if (changes > 0) {{
            let up = 0, down = 0;
            for (const [, pct] of Object.entries(lastPrices)) {{
                if (pct > 0) up++;
                else if (pct < 0) down++;
            }}
            const udEl = document.getElementById('up-down');
            if (udEl) udEl.textContent = up + '\u6da8' + down + '\u8dcc';
        }}

        updateCount++;
        const liveText = document.getElementById('live-text');
        if (liveText) {{
            liveText.textContent = '\u5b9e\u65f6 \u00b7 ' + new Date().toLocaleTimeString('zh-CN',
                {{hour:'2-digit',minute:'2-digit',second:'2-digit'}});
        }}
        return changes;
    }}

    async function refreshLoop() {{
        try {{
            const data = await fetchPrices();
            updatePrices(data);
        }} catch(e) {{ console.warn('[Live] Refresh error:', e.message); }}
        setTimeout(refreshLoop, REFRESH_INTERVAL);
    }}

    refreshLoop();

    document.addEventListener('click', function(e) {{
        if (!e.target.classList.contains('hib')) {{
            document.querySelectorAll('.hp').forEach(function(p) {{ p.style.display = 'none'; }});
        }}
    }});
    </script>"""


# ============================================================
# 颜色/徽章映射
# ============================================================
STAGE_STYLE = {
    "主升": ("#C4433A15", "#C4433A", "🔥"),
    "强化": ("#E87A2015", "#E87A20", "📈"),
    "持续": ("#3E54CE15", "#3E54CE", "➡️"),
    "孵化": ("#7C4FC415", "#7C4FC4", "🌱"),
}

HEAT_COLOR = {
    "high": "#C4433A",    # >= 80
    "mid": "#E87A20",     # >= 60
    "low": "#3E54CE",     # < 60
}

TIER_STYLE = {
    1: ("龙头首选", "l1"),
    2: ("弹性机会", "l2"),
    3: ("相关标的", "l3"),
}

EDITION_META = {
    "am": {"label": "晨会版", "icon": "🌅", "badge": "国内版 🧡", "time": "交易日7:00更新"},
    "md": {"label": "午间版", "icon": "☀️", "badge": "国内版 🧡", "time": "交易日12:00更新"},
    "pm": {"label": "晚间版", "icon": "🌙", "badge": "国内版 🧡", "time": "每晚20:00更新"},
    "global": {"label": "全球版", "icon": "🌍", "badge": "全球版 🌐", "time": "每日8:00更新"},
}


# ============================================================
# HTML 片段渲染函数
# ============================================================

def _heat_color(score: int) -> str:
    if score >= 80:
        return HEAT_COLOR["high"]
    elif score >= 60:
        return HEAT_COLOR["mid"]
    return HEAT_COLOR["low"]


def render_header(meta: Dict) -> str:
    """报告头部：渐变背景 + 版本标签 + 实时脉搏"""
    edition = EDITION_META.get(meta.get("edition", "am"), EDITION_META["am"])
    return f"""<div class="sh">
<div class="sd">⚡ 蓝宝书Max · 每日机构投研精华</div>
<div class="sh1">机构观点快照<span class="vb dom">{edition['badge']}</span>
<span class="live-dot" id="live-dot"></span><span class="live-text" id="live-text">实时行情</span></div>
<div style="font-size:13px;color:rgba(255,255,255,.85);margin-top:4px;font-weight:500">
📋 {meta.get('date_display', '')} {edition['label']} · {meta['topic_count']}主题 · 覆盖沪深A股 · 实时刷新</div>
<div class="sm">
<div class="smi"><strong>{meta['topic_count']}</strong> 全部主题</div>
<div class="smi"><strong>{meta.get('opp_count', 0)}</strong> 机会前瞻</div>
<div class="smi"><strong>{meta.get('stock_count', 0)}</strong> 推荐标的</div>
</div></div>"""


def render_market_summary(summary: Dict) -> str:
    """市场情绪速览卡片"""
    if not summary:
        return ""

    top_dirs = summary.get("top_directions", [])
    rising_tags = summary.get("rising_tags", [])
    one_liner = summary.get("one_liner", "")
    up_count = summary.get("up_count", 0)
    down_count = summary.get("down_count", 0)
    total_topics = summary.get("total_topics", 0)
    total_opp = summary.get("total_opp", 0)
    total_stocks = summary.get("total_stocks", 0)

    # 最强方向
    top_parts = []
    for i, (name, heat) in enumerate(top_dirs[:3]):
        top_parts.append(f"【{name}】热度{heat}")
    top_str = " · ".join(top_parts)

    # 涨跌标签
    tags_html = ""
    for tag in rising_tags:
        tags_html += f'<span class="tag-s">↑ {tag}</span>'

    return f"""<div class="sc">
<div style="font-size:12px;font-weight:700;color:#C47A00;margin-bottom:4px">📋 今日市场摘要</div>
<div class="st">最强方向：{top_str}</div>
<div class="sm2">
<div class="smi2"><strong>{total_topics}</strong> 全部主题 · <strong>{total_opp}</strong> 机会前瞻 · <strong>{total_stocks}</strong> 推荐标的 · <span id="up-down">{up_count}涨{down_count}跌</span></div>
</div>
<div class="chg">{tags_html}</div>
<div style="font-size:12px;color:#666;margin-top:6px;line-height:1.5;font-weight:500">📌 一句话总结：{one_liner}</div>
</div>"""


def render_topic_card(topic: Dict, popup_id: str) -> str:
    """单个主题卡片"""
    rank = topic.get("rank", 0)
    title = topic.get("title", "")
    stage = topic.get("stage", "持续")
    stage_bg, stage_color, stage_icon = STAGE_STYLE.get(stage, STAGE_STYLE["持续"])
    heat = topic.get("heat", 0)
    hc = _heat_color(heat)

    # 热度拆解
    hb = topic.get("heat_breakdown", {})
    org = hb.get("机构关注度", 0)
    mkt = hb.get("市场确认度", 0)
    cat = hb.get("催化质量", 0)

    # AI摘要 & 蓝宝书原文
    ai_summary = topic.get("ai_summary", "")
    bluebook_quote = topic.get("bluebook_quote", "")

    # 标的分组
    stock_groups = topic.get("stock_groups", [])

    # 构建 HTML
    parts = [f"""<div class="tc">
<div class="th">
<span class="tr">TOP{rank}</span>
<span class="tn">{title}</span>
<span class="sb" style="background:{stage_bg};color:{stage_color}">{stage_icon}{stage}</span>
<span class="ts">
<span class="tsv" style="color:{hc}">{heat}</span>
<span class="hib" data-popup="{popup_id}" onclick="event.stopPropagation();var p=document.getElementById('{popup_id}');p.style.display=p.style.display==='block'?'none':'block';">ⓘ</span>
<div class="hp" id="{popup_id}">
<div class="pt">{title} · 热度指数构成</div>
<div class="pb">机构关注度 {org} | 市场确认度 {mkt} | 催化质量 {cat}</div>
</div>
</span>
</div>"""]

    # AI 摘要
    if ai_summary:
        parts.append(f'<div class="tr2">📌 {ai_summary}</div>')

    # 蓝宝书原文
    if bluebook_quote:
        parts.append(f'<div class="tbb">📘 "{bluebook_quote}"</div>')

    # 产业链分析
    chain = topic.get("industry_chain")
    if chain and chain.get("nodes"):
        parts.append(_render_chain_section(chain))

    # 标的分层
    if stock_groups:
        parts.append('<div class="tsl">')
        for group in stock_groups:
            tier = group.get("tier", 1)
            tier_label, tier_class = TIER_STYLE.get(tier, (f"层级{tier}", "l3"))
            stocks = group.get("stocks", [])
            if not stocks:
                continue

            parts.append(f'<div class="t-sg"><div class="t-gl {tier_class}">{tier_label}</div>')
            for s in stocks:
                name = s.get("name", "")
                code = s.get("code", "")
                pct = s.get("pct", 0)
                reason = s.get("reason", "")
                pct_str, dir_class = _fmt_pct(pct)
                tsc_cls = f"tsc {dir_class}".rstrip()

                parts.append(f'<div class="tsr" data-stock="{name}">'
                           f'<span class="tsn">{name}</span>'
                           f'<span class="tcd">{code}</span>'
                           f'<span class="{tsc_cls}" data-field="pct">{pct_str}</span>'
                           f'<span class="tsr2">{reason}</span>'
                           f'</div>')
            parts.append('</div>')
        parts.append('</div>')

    parts.append('</div>')
    return "\n".join(parts)


def render_opportunity_preview(opp: Dict, popup_id: str) -> str:
    """机会前瞻卡片（特殊紫色左边框样式）"""
    title = opp.get("title", "")
    stage = opp.get("stage", "孵化")
    _, stage_color, stage_icon = STAGE_STYLE.get(stage, STAGE_STYLE["孵化"])
    heat = opp.get("heat", 0)
    hc = _heat_color(heat)

    hb = opp.get("heat_breakdown", {})
    org = hb.get("机构关注度", 0)
    mkt = hb.get("市场确认度", 0)
    cat = hb.get("催化质量", 0)

    ai_summary = opp.get("ai_summary", "")
    bluebook_quote = opp.get("bluebook_quote", "")
    stocks = opp.get("stocks", [])

    parts = [f"""<div class="tc" style="border-left:3px solid #9B59B6">
<div class="th">
<span class="tn" style="font-size:16px">{title}</span>
<span class="sb" style="background:#8B5CF615;color:#8B5CF6">{stage_icon}{stage}</span>
<span class="ts">
<span class="tsv" style="color:#8B5CF6">{heat}</span>
<span class="hib" data-popup="{popup_id}" onclick="event.stopPropagation();var p=document.getElementById('{popup_id}');p.style.display=p.style.display==='block'?'none':'block';">ⓘ</span>
<div class="hp" id="{popup_id}">
<div class="pt">{title} · 热度指数构成</div>
<div class="pb">机构关注度 {org} | 市场确认度 {mkt} | 催化质量 {cat}</div>
</div>
</span>
</div>"""]

    if ai_summary:
        parts.append(f'<div class="tr2">📌 {ai_summary}</div>')

    if bluebook_quote:
        parts.append(f'<div class="tbb" style="border-left-color:#9B59B6">📘 "{bluebook_quote}"</div>')

    if stocks:
        parts.append('<div class="tsl">')
        for s in stocks:
            name = s.get("name", "")
            code = s.get("code", "")
            pct = s.get("pct", 0)
            reason = s.get("reason", "")
            pct_str, dir_class = _fmt_pct(pct)
            tsc_cls = f"tsc {dir_class}".rstrip()

            parts.append(f'<div class="tsr" data-stock="{name}">'
                       f'<span class="tsn">{name}</span>'
                       f'<span class="tcd">{code}</span>'
                       f'<span class="{tsc_cls}" data-field="pct">{pct_str}</span>'
                       f'<span class="tsr2">{reason}</span>'
                       f'</div>')
        parts.append('</div>')

    parts.append('</div>')
    return "\n".join(parts)


def _fmt_pct(pct: float) -> tuple:
    """格式化涨跌幅，返回 (显示字符串, dir_class)"""
    if pct == 0:
        return ("-0.00%", "")
    pct_str = f"+{pct:.2f}%" if pct > 0 else f"{pct:.2f}%"
    dir_class = "up" if pct > 0 else "dn"
    return (pct_str, dir_class)


def _render_chain_section(chain: Dict) -> str:
    """产业链分析区块"""
    if not chain or not chain.get("nodes"):
        return ""

    parts = ['<div class="tsl" style="margin-top:8px">'
             '<div class="t-sg">'
             '<div class="t-gl" style="background:#7C4FC412;color:#7C4FC4;font-size:11px">'
             '🔗 产业链分析</div>']

    for node in chain.get("nodes", []):
        node_stocks = node.get("stocks", [])
        if not node_stocks:
            continue
        level = node.get("level", "")
        role = node.get("role", "")
        parts.append(
            f'<div style="font-size:11px;color:#7C4FC4;margin:4px 0 2px;font-weight:600">'
            f'{level} {role}</div>'
        )
        for s in node_stocks:
            parts.append(
                f'<div class="tsr" data-stock="{s["name"]}" '
                f'style="font-size:11px;padding:2px 0;border-bottom:1px dashed #F0EEF8">'
                f'<span class="tsn" style="font-size:12px;font-weight:600">{s["name"]}</span>'
                f'<span class="tcd">{s.get("code", "")}</span>'
                f'<span class="tsr2" style="color:#7C4FC4;font-style:italic">{s.get("catalyst", "")}</span>'
                f'</div>'
            )

    parts.append('</div></div>')
    return "\n".join(parts)


def render_alpha_row(stock: Dict, is_leader: bool = False) -> str:
    """Alpha 精选行"""
    name = stock.get("name", "")
    alpha = stock.get("alpha", 0)
    reason = stock.get("reason", "")
    pct = stock.get("pct", 0)

    pct_str, dir_class = _fmt_pct(pct)
    star = "★" if is_leader else "·"
    star_cls = f"ar ldr" if is_leader else "ar"
    ap_cls = f"ap {dir_class}".rstrip()

    return f'''<div class="asc">
<span class="{star_cls}">{star}</span>
<div class="ai"><span class="an">{name}</span><span class="ab">{alpha}</span><span class="ar2">{reason}</span></div>
<div class="{ap_cls}" data-stock="{name}" data-field="pct">{pct_str}</div>
</div>'''


def render_footer(meta: Dict) -> str:
    """页脚"""
    edition_label = EDITION_META.get(meta.get("edition", "am"), {}).get("label", "")
    date_display = meta.get("date_display", "")
    return f"""<div class="fo">
<div>⚡ 蓝宝书Max · {date_display} {edition_label} · 数据来源：Alpha派蓝宝书 · 行情：东方财富</div>
<div class="fl">📊 热度指数=机构关注度+市场确认度+催化质量 · 📌 阶段判定：🔥📈➡️🌱<br>
🟢 实时行情每3秒自动刷新 · ★ Alpha=催化质量+主题热度+产业地位+市场确认 · ⚠️ 仅供参考</div>
</div>"""


# ============================================================
# 主渲染函数
# ============================================================

def generate_report(report_data: Dict) -> str:
    """
    从结构化数据生成完整 HTML 报告

    report_data 结构:
    {
        "meta": {
            "edition": "am",          # am|md|pm|global
            "date": "2026-06-23",
            "date_display": "2026年6月23日",
            "topic_count": 20,
            "opp_count": 2,
            "stock_count": 137,
            "title": "蓝宝书Max · 2026年6月23日 晨会版"
        },
        "market_summary": {
            "top_directions": [("氧化锆断供", 92), ...],
            "rising_tags": ["氧化锆断供", ...],
            "one_liner": "...",
            "up_count": 81, "down_count": 54,
            "total_topics": 20, "total_opp": 2, "total_stocks": 137
        },
        "topics": [
            {
                "rank": 1,
                "title": "...",
                "stage": "主升",       # 主升|强化|持续|孵化
                "heat": 92,
                "heat_breakdown": {"机构关注度": 60, "市场确认度": 18, "催化质量": 14},
                "ai_summary": "...",
                "bluebook_quote": "...",
                "stock_groups": [
                    {"tier": 1, "stocks": [{"name": "...", "code": "...", "pct": 19.99, "reason": "..."}]},
                    ...
                ]
            },
            ...
        ],
        "opportunity_previews": [...],   # 结构同 topics 但用 stocks 列表
        "top5_alpha": [...],            # [{"name":..., "alpha":..., "reason":..., "pct":...}]
        "all_alpha": [...],
        "secid_map": {"股票名": "0.300xxx", ...}
    }
    """
    meta = report_data.get("meta", {})
    title = meta.get("title", "蓝宝书Max")

    # 构建 HTML
    html_parts = [f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<style>{REPORT_CSS}</style></head>
<body>
<div class="w">"""]

    # 1. 头部
    html_parts.append(render_header(meta))

    # 2. 正文区域
    html_parts.append('<div class="ct">')

    # 2a. 市场摘要
    market_summary = report_data.get("market_summary")
    if market_summary:
        html_parts.append(render_market_summary(market_summary))

    # 2b. 全部主题
    topics = report_data.get("topics", [])
    if topics:
        html_parts.append(
            '<div class="s2"><span>🔥 全部主题（{}个）</span>'
            '<span style="font-size:10px;font-weight:400;color:#999;background:#F5F4F2;padding:3px 8px;border-radius:4px">'
            '点击ⓘ查看三维度评分</span></div>'.format(len(topics))
        )
        html_parts.append('<div class="grid">')
        for i, topic in enumerate(topics):
            html_parts.append(render_topic_card(topic, f"popup-{i}"))
        html_parts.append('</div>')

    # 2c. 机会前瞻
    opps = report_data.get("opportunity_previews", [])
    if opps:
        html_parts.append(
            '<div class="s2" style="margin-top:4px">🔮 机会前瞻 '
            '<span style="font-size:11px;font-weight:400;color:#999;margin-left:6px">'
            '机构新增关注、逐渐发酵的新话题</span></div>'
        )
        html_parts.append('<div class="grid" style="margin-bottom:20px">')
        for i, opp in enumerate(opps):
            html_parts.append(render_opportunity_preview(opp, f"hp_opp_{i}"))
        html_parts.append('</div>')

    # 2d. Top5 Alpha
    top5 = report_data.get("top5_alpha", [])
    if top5:
        html_parts.append(
            '<div class="s2" style="margin-top:20px">★ 今日Top5 Alpha'
            '<span style="font-size:10px;font-weight:400;color:#999;background:#F5F4F2;'
            'padding:3px 8px;border-radius:4px;margin-left:6px">综合催化质量·主题热度·产业地位·市场确认</span></div>'
        )
        html_parts.append('<div class="alpha-list">')
        for s in top5:
            html_parts.append(render_alpha_row(s, is_leader=True))
        html_parts.append('</div>')

    # 2e. 全部 Alpha (精简)
    all_alpha = report_data.get("all_alpha", [])
    if all_alpha:
        html_parts.append(
            f'<div class="s2" style="margin-top:14px;font-size:14px">'
            f'📋 Alpha精选池（{len(all_alpha)}只 · 按综合评分排序）</div>'
        )
        html_parts.append('<div class="alpha-list">')
        for s in all_alpha:
            html_parts.append(render_alpha_row(s, is_leader=False))
        html_parts.append('</div>')

    html_parts.append('</div>')  # close .ct

    # 3. 页脚
    html_parts.append(render_footer(meta))

    html_parts.append('</div>')  # close .w

    # 4. 实时行情 JS
    secid_map = report_data.get("secid_map", {})
    html_parts.append(render_live_js(secid_map))

    html_parts.append('</body></html>')

    return "\n".join(html_parts)


# ============================================================
# CLI 入口（用于测试）
# ============================================================
if __name__ == "__main__":
    import sys
    from pathlib import Path

    # 测试：从 sample data 生成
    sample = {
        "meta": {
            "edition": "am", "date": "2026-06-23",
            "date_display": "2026年6月23日 晨会版",
            "topic_count": 3, "opp_count": 1, "stock_count": 15,
            "title": "蓝宝书Max · 2026年6月23日 晨会版"
        },
        "market_summary": {
            "top_directions": [("测试主题A", 85), ("测试主题B", 72), ("测试主题C", 68)],
            "rising_tags": ["测试主题A", "测试主题B"],
            "one_liner": "测试一句话总结",
            "up_count": 10, "down_count": 5,
            "total_topics": 3, "total_opp": 1, "total_stocks": 15
        },
        "topics": [
            {
                "rank": 1, "title": "测试主题A", "stage": "主升", "heat": 85,
                "heat_breakdown": {"机构关注度": 50, "市场确认度": 20, "催化质量": 15},
                "ai_summary": "测试AI总结内容",
                "bluebook_quote": "测试蓝宝书原文引用",
                "stock_groups": [
                    {"tier": 1, "stocks": [
                        {"name": "测试股A", "code": "000001", "pct": 5.23, "reason": "测试推荐理由"}
                    ]},
                    {"tier": 2, "stocks": [
                        {"name": "测试股B", "code": "000002", "pct": -2.15, "reason": "测试弹性推荐"}
                    ]}
                ]
            }
        ],
        "opportunity_previews": [
            {
                "title": "测试前瞻", "stage": "孵化", "heat": 32,
                "heat_breakdown": {"机构关注度": 12, "市场确认度": 10, "催化质量": 10},
                "ai_summary": "测试前瞻摘要",
                "bluebook_quote": "测试前瞻引用",
                "stocks": [
                    {"name": "测试股C", "code": "000003", "pct": 1.50, "reason": "测试前瞻推荐"}
                ]
            }
        ],
        "top5_alpha": [
            {"name": "测试股A", "alpha": 82, "reason": "测试推荐", "pct": 5.23}
        ],
        "all_alpha": [
            {"name": "测试股B", "alpha": 65, "reason": "测试", "pct": -2.15}
        ],
        "secid_map": {"测试股A": "0.000001", "测试股B": "0.000002", "测试股C": "0.000003"}
    }

    html = generate_report(sample)

    out_dir = Path("output/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "am-test-v3.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[render_engine] Test report written to {out_path}")
    print(f"[render_engine] HTML size: {len(html):,} bytes")
