#!/usr/bin/env python3
"""
蓝宝书Max 报告生成器
====================
读取 data-{edition}-YYYYMMDD.json，生成带行情数据的 HTML 报告。

用法:
  python3 generate_report.py --edition am
  python3 generate_report.py --edition am --data data-am-20260623.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path.cwd()

# HTML 模板
# 付费墙 CSS（注入到每个报告页面）
PAYWALL_CSS = """
.pw-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.55);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);z-index:10000;display:flex;align-items:center;justify-content:center;animation:pwFadeIn .3s ease}
@keyframes pwFadeIn{from{opacity:0}to{opacity:1}}
.pw-card{background:#fff;border-radius:24px;padding:48px 40px;max-width:420px;width:92%;text-align:center;box-shadow:0 24px 80px rgba(0,0,0,.18);animation:pwSlideUp .4s cubic-bezier(.16,1,.3,1)}
@keyframes pwSlideUp{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}
.pw-icon{font-size:52px;margin-bottom:16px}
.pw-title{font-size:22px;font-weight:700;color:#1D1D1F;margin-bottom:12px}
.pw-desc{font-size:14px;color:#86868B;line-height:1.7;margin-bottom:28px}
.pw-input-group{display:flex;gap:8px;margin-bottom:12px}
.pw-input{flex:1;padding:12px 16px;border:1.5px solid #E5E5EA;border-radius:12px;font-size:15px;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;text-align:center;letter-spacing:2px;outline:none;transition:border-color .15s}
.pw-input:focus{border-color:#0071E3}
.pw-btn{padding:12px 24px;background:#0071E3;color:#fff;border:none;border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;transition:all .15s;white-space:nowrap;font-family:inherit}
.pw-btn:hover{background:#0077ED}
.pw-btn:disabled{opacity:.6;cursor:not-allowed}
.pw-error{color:#FF3B30;font-size:13px;margin-top:8px;display:none}
.pw-footer{margin-top:28px;padding-top:20px;border-top:1px solid #F2F2F7}
.pw-footer p{font-size:13px;color:#AEAEB2;margin-bottom:10px}
.pw-zsxq-btn{display:inline-flex;align-items:center;gap:6px;padding:10px 24px;background:linear-gradient(135deg,#1AAD19,#0F8F0F);color:#fff;border-radius:12px;text-decoration:none;font-size:14px;font-weight:600;transition:all .15s}
.pw-zsxq-btn:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(26,173,25,.3)}
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN" data-paywall="true">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>蓝宝书Max - {edition_label} - {date_display}</title>
    <style>
        """ + PAYWALL_CSS + """
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            background: #f0f2f5;
            color: #1a1a2e;
            line-height: 1.7;
            min-height: 100vh;
        }}

        /* 顶部导航 */
        .top-nav {{
            background: #fff;
            border-bottom: 1px solid #e8ecf1;
            padding: 0 24px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .top-nav .brand {{
            font-weight: 700;
            font-size: 15px;
            color: #1a73e8;
            text-decoration: none;
        }}
        .top-nav .brand span {{ color: #f59e0b; }}
        .top-nav a {{ font-size: 13px; color: #64748b; text-decoration: none; }}
        .top-nav a:hover {{ color: #1a73e8; }}

        .container {{ max-width: 1000px; margin: 0 auto; padding: 24px 20px 60px; }}

        /* 报告头部 */
        .report-header {{
            background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
            color: white;
            padding: 36px 32px;
            border-radius: 16px;
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
        }}
        .report-header::after {{
            content: "";
            position: absolute;
            right: -40px; top: -40px;
            width: 200px; height: 200px;
            background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
            border-radius: 50%;
        }}
        .report-header * {{ position: relative; z-index: 1; }}
        .report-header .edition-tag {{
            display: inline-block;
            background: rgba(255,255,255,0.18);
            padding: 3px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            margin-bottom: 10px;
            letter-spacing: 1px;
        }}
        .report-header h1 {{
            font-size: 30px;
            font-weight: 800;
            margin-bottom: 6px;
            letter-spacing: -0.5px;
        }}
        .report-header .meta-row {{
            display: flex;
            gap: 24px;
            font-size: 13px;
            opacity: 0.85;
            margin-top: 8px;
        }}

        /* 概览卡片 */
        .overview-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }}
        .overview-card {{
            background: #fff;
            border-radius: 12px;
            padding: 18px 16px;
            text-align: center;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
            border: 1px solid #e8ecf1;
        }}
        .overview-card .num {{
            font-size: 28px;
            font-weight: 800;
            color: #1a73e8;
            line-height: 1.2;
        }}
        .overview-card .label {{
            font-size: 12px;
            color: #94a3b8;
            margin-top: 4px;
        }}
        .overview-card.up .num {{ color: #e74c3c; }}
        .overview-card.down .num {{ color: #27ae60; }}

        /* 板块 */
        .section {{
            background: #fff;
            border-radius: 14px;
            padding: 28px;
            margin-bottom: 20px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
            border: 1px solid #e8ecf1;
        }}
        .section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 2px solid #f0f2f5;
        }}
        .section-header h2 {{
            font-size: 18px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .section-header .count {{
            font-size: 13px;
            color: #94a3b8;
            font-weight: 400;
        }}

        /* 股票网格 */
        .stock-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
            gap: 12px;
        }}
        .stock-card {{
            border: 1px solid #e8ecf1;
            border-radius: 12px;
            padding: 18px 16px;
            text-align: center;
            transition: all 0.25s;
            background: #fafbfc;
            position: relative;
            overflow: hidden;
        }}
        .stock-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 8px 24px rgba(26,115,232,0.1);
            border-color: #1a73e8;
            background: #fff;
        }}
        .stock-card .market-dot {{
            position: absolute;
            top: 10px; right: 12px;
            width: 8px; height: 8px;
            border-radius: 50%;
        }}
        .market-dot.sh {{ background: #e74c3c; }}
        .market-dot.sz {{ background: #3498db; }}
        .stock-name {{
            font-size: 16px;
            font-weight: 700;
            color: #1a1a2e;
            margin-bottom: 2px;
        }}
        .stock-code {{
            font-size: 11px;
            color: #94a3b8;
            margin-bottom: 10px;
            font-family: "SF Mono", "Menlo", monospace;
        }}
        .stock-price {{
            font-size: 26px;
            font-weight: 800;
            color: #1a1a2e;
            line-height: 1.2;
        }}
        .stock-price .currency {{ font-size: 13px; font-weight: 400; color: #94a3b8; }}
        .stock-change {{
            font-size: 14px;
            font-weight: 600;
            margin-top: 6px;
            padding: 2px 10px;
            border-radius: 20px;
            display: inline-block;
        }}
        .up {{ color: #e74c3c; background: #fff0f0; }}
        .down {{ color: #27ae60; background: #f0fff0; }}
        .neutral {{ color: #94a3b8; background: #f8f9fa; }}

        /* 热点列表 */
        .topic-list {{ display: flex; flex-direction: column; gap: 12px; }}
        .topic-item {{
            border: 1px solid #e8ecf1;
            border-radius: 12px;
            padding: 18px 20px;
            transition: all 0.2s;
            background: #fafbfc;
        }}
        .topic-item:hover {{
            border-color: #cbd5e1;
            background: #fff;
        }}
        .topic-index {{
            display: inline-block;
            width: 26px; height: 26px;
            border-radius: 50%;
            background: #1a73e8;
            color: #fff;
            font-size: 12px;
            font-weight: 700;
            text-align: center;
            line-height: 26px;
            margin-right: 8px;
            flex-shrink: 0;
        }}
        .topic-item h3 {{
            font-size: 15px;
            font-weight: 600;
            color: #1a1a2e;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
        }}
        .topic-item .topic-body {{
            font-size: 13px;
            color: #64748b;
            line-height: 1.6;
            margin-left: 34px;
        }}
        .topic-item .topic-meta {{
            font-size: 11px;
            color: #94a3b8;
            margin-left: 34px;
            margin-top: 6px;
        }}

        /* 原始文本 */
        .raw-text {{
            white-space: pre-wrap;
            font-size: 13px;
            color: #475569;
            line-height: 1.8;
            max-height: 500px;
            overflow-y: auto;
            border: 1px solid #e8ecf1;
            border-radius: 10px;
            padding: 20px;
            background: #f8f9fa;
            font-family: "SF Mono", "Menlo", "Monaco", monospace;
        }}

        .empty-state {{
            text-align: center;
            color: #94a3b8;
            padding: 48px 20px;
        }}
        .empty-state .icon {{ font-size: 40px; margin-bottom: 12px; }}
        .empty-state p {{ font-size: 14px; }}

        .report-footer {{
            text-align: center;
            color: #94a3b8;
            font-size: 12px;
            padding: 32px 20px;
            border-top: 1px solid #e8ecf1;
            margin-top: 20px;
        }}
        .report-footer a {{ color: #1a73e8; text-decoration: none; }}

        /* 响应式 */
        @media (max-width: 600px) {{
            .report-header h1 {{ font-size: 22px; }}
            .report-header .meta-row {{ flex-direction: column; gap: 4px; }}
            .stock-grid {{ grid-template-columns: 1fr 1fr; }}
            .stock-price {{ font-size: 20px; }}
            .section {{ padding: 20px 16px; }}
        }}
    </style>
</head>
<body>

<!-- 付费墙容器（未认证时自动弹出） -->
<div id="paywall-container"></div>

<!-- 顶部导航 -->
<nav class="top-nav">
    <a href="index.html" class="brand">📘 蓝宝书<span>Max</span></a>
    <a href="index.html">← 返回导航页</a>
</nav>

<div class="container">
    <!-- 报告头部 -->
    <div class="report-header">
        <div class="edition-tag">{edition_tag}</div>
        <h1>{edition_label}版 · 蓝宝书热点报告</h1>
        <div class="meta-row">
            <span>📅 {date_display}</span>
            <span>⏰ {scrape_time}</span>
            <span>📊 {stock_count} 只相关股票</span>
        </div>
    </div>

    <!-- 概览卡片 -->
    <div class="overview-row">
        <div class="overview-card">
            <div class="num">{topic_count}</div>
            <div class="label">热点主题</div>
        </div>
        <div class="overview-card">
            <div class="num">{stock_count}</div>
            <div class="label">相关股票</div>
        </div>
        <div class="overview-card {market_direction}">
            <div class="num">{up_count}</div>
            <div class="label">上涨</div>
        </div>
        <div class="overview-card {market_direction_down}">
            <div class="num">{down_count}</div>
            <div class="label">下跌</div>
        </div>
    </div>

    <!-- 股票行情 -->
    <div class="section">
        <div class="section-header">
            <h2>📈 相关股票行情</h2>
            <span class="count">{stock_count} 只</span>
        </div>
        {stocks_html}
    </div>

    <!-- 热点主题 -->
    <div class="section">
        <div class="section-header">
            <h2>🔥 热点主题</h2>
            <span class="count">{topic_count} 条</span>
        </div>
        {topics_html}
    </div>

    <!-- 原始内容 -->
    {raw_html}

    <div class="report-footer">
        蓝宝书Max · 自动化报告 · 数据来源: 
        <a href="https://www.alphapai.com" target="_blank">Alpha派</a> & 
        <a href="https://www.eastmoney.com" target="_blank">东方财富</a>
    </div>
</div>

<script src="/bluebook-max/paywall.js"></script>

</body>
</html>"""

EDITION_LABELS = {"am": "晨会", "md": "午间", "pm": "晚间"}


def render_stocks(stocks: list[dict]) -> str:
    """渲染股票卡片"""
    if not stocks:
        return '<div class="empty">暂未提取到相关股票</div>'

    cards = []
    for s in stocks:
        name = s.get("name", "?")
        code = s.get("code", "?")
        market = s.get("market", "")
        market_badge = '<span class="badge badge-sh">沪</span>' if market == "SH" else '<span class="badge badge-sz">深</span>'
        price = s.get("price")
        change_pct = s.get("change_pct")
        change_val = s.get("change_val")

        if price is not None:
            try:
                price_f = float(price)
                price_str = f"¥{price_f:.2f}"
            except (ValueError, TypeError):
                price_str = f"¥{price}"
        else:
            price_str = "N/A"

        if change_pct is not None:
            try:
                pct_f = float(change_pct)
                direction = "up" if pct_f > 0 else "down" if pct_f < 0 else ""
                sign = "+" if pct_f > 0 else ""
                change_str = f'{sign}{pct_f:.2f}%'
            except (ValueError, TypeError):
                direction = ""
                change_str = f"{change_pct}%"
        else:
            direction = ""
            change_str = "N/A"

        cards.append(f"""
        <div class="stock-card">
            <div class="stock-name">{name}</div>
            <div class="stock-code">{code} {market_badge}</div>
            <div class="stock-price">{price_str}</div>
            <div class="stock-change {direction}">{change_str}</div>
        </div>""")

    return f'<div class="stock-grid">{"".join(cards)}</div>'


def render_topics(raw_topics: list) -> str:
    """渲染热点主题"""
    if not raw_topics:
        return '<div class="empty">未获取到结构化热点数据</div>'

    items = []
    for i, topic in enumerate(raw_topics[:20]):  # 最多显示 20 条
        if isinstance(topic, dict):
            title = topic.get("title") or topic.get("name") or topic.get("topic") or f"主题 #{i+1}"
            content = topic.get("content") or topic.get("summary") or topic.get("desc") or ""
            # 如果有其他字段，也显示
            extra = ""
            for k, v in topic.items():
                if k not in ("title", "name", "topic", "content", "summary", "desc") and v:
                    extra += f'<span style="color:#95a5a6;font-size:12px;">{k}: {v}</span> '
            items.append(f'<div class="topic-item"><h3>📌 {title}</h3><p>{str(content)[:500]}</p>{extra}</div>')
        elif isinstance(topic, str):
            items.append(f'<div class="topic-item"><p>{topic[:500]}</p></div>')

    return "".join(items) if items else '<div class="empty">热点数据为空</div>'


def generate_report(data_file: str, edition: str) -> str:
    """生成 HTML 报告"""
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("meta", {})
    stocks = data.get("stocks", [])
    raw_topics = data.get("raw_topics", [])
    raw_text = data.get("raw_text")

    # 日期信息
    date_str = meta.get("scrape_time", "")[:10] or datetime.now().strftime("%Y-%m-%d")
    date_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y年%m月%d日") if len(date_str) == 10 else date_str
    scrape_time = meta.get("scrape_time", "N/A")
    edition_label = EDITION_LABELS.get(edition, edition.upper())
    edition_tags = {"am": "🌅 晨会版", "md": "☀️ 午间版", "pm": "🌙 晚间版"}

    # 统计涨跌
    up_count = 0
    down_count = 0
    for s in stocks:
        pct = s.get("change_pct")
        if pct is not None:
            try:
                if float(pct) > 0:
                    up_count += 1
                elif float(pct) < 0:
                    down_count += 1
            except (ValueError, TypeError):
                pass

    market_direction = "up" if up_count > down_count else "down" if down_count > up_count else ""
    market_direction_down = "down" if down_count > up_count else ""

    # 渲染各部分
    stocks_html = render_stocks(stocks)
    topics_html = render_topics(raw_topics)
    topic_count = len(raw_topics) if raw_topics else 0

    # 原始文本（如果没有结构化数据）
    raw_html = ""
    if not raw_topics and raw_text:
        raw_html = f"""
        <div class="section">
            <div class="section-header"><h2>📝 原始内容</h2></div>
            <div class="raw-text">{raw_text}</div>
        </div>"""

    # 填充模板
    html = HTML_TEMPLATE.format(
        edition=edition,
        edition_label=edition_label,
        edition_tag=edition_tags.get(edition, edition_label),
        date_display=date_display,
        scrape_time=scrape_time[:19] if scrape_time else "N/A",
        stock_count=len(stocks),
        topic_count=topic_count,
        up_count=up_count,
        down_count=down_count,
        market_direction=market_direction,
        market_direction_down=market_direction_down,
        stocks_html=stocks_html,
        topics_html=topics_html,
        raw_html=raw_html,
    )

    # 保存
    report_file = OUTPUT_DIR / f"{edition}-{date_str.replace('-', '')}.html"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 报告已生成: {report_file}")
    return str(report_file)


def find_data_file(edition: str) -> str:
    """自动查找最新的 JSON 数据文件"""
    pattern = f"data-{edition}-*.json"
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    if not files:
        print(f"❌ 未找到数据文件 (pattern: {pattern})")
        sys.exit(1)
    return str(files[0])


def main():
    parser = argparse.ArgumentParser(description="蓝宝书Max 报告生成器")
    parser.add_argument("--edition", choices=["am", "md", "pm"], default="am", help="蓝宝书版本")
    parser.add_argument("--data", help="指定数据文件路径（默认自动查找最新的）")
    args = parser.parse_args()

    data_file = args.data or find_data_file(args.edition)
    print(f"📄 读取数据: {data_file}")

    report_file = generate_report(data_file, args.edition)

    return report_file


if __name__ == "__main__":
    main()
