#!/usr/bin/env python3
"""
蓝宝书Max · 报告构建器
输入: Alpha派 JSON 数据 + 东方财富实时行情
输出: 符合 README 规范的 ED JSON → 注入 template.html → 最终 HTML
"""
import json, re, sys, subprocess, time as _time
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from generate_real_report import parse_reports, _parse_stock_reasons, build_secid_map
from stock_secid import get_secid
from industry_chain import match_chain

CST = timezone(timedelta(hours=8))
TEMPLATE = Path("template.html")
DATA_JSON = Path("data/reports_2026-06-23.json")
MD_DATA_JSON = Path("data/md_complete_data.json")
OUTPUT_DIR = Path("output/reports")

# ============================================================
# 评分引擎 (README 规范)
# ============================================================

def score_topic_v3(topic_data, live_prices):
    """三层独立评分: 机构关注0-60 + 市场确认0-25 + 催化强度0-15"""
    heat_raw = topic_data["heat"]  # Alpha派 index (1-10)
    summary = topic_data.get("summary_clean", topic_data.get("summary_raw", ""))

    # 机构关注度 (0-60): Alpha派 index / 10 * 60
    org = int(heat_raw / 10 * 60)

    # 市场确认度 (0-25): 标的均价涨跌幅绝对值
    market = 5
    stocks = topic_data.get("stocks", [])
    if live_prices and stocks:
        pcts = []
        for name in stocks:
            if name in live_prices:
                p = live_prices[name].get("change_pct", 0)
                if isinstance(p, (int, float)):
                    pcts.append(abs(p))
        if pcts:
            avg = sum(pcts) / len(pcts)
            if avg >= 5: market = 25
            elif avg >= 3: market = 18
            elif avg >= 1: market = 10

    # 催化强度 (0-15): 关键词匹配
    if any(kw in summary for kw in ["官宣", "确认", "正式发布", "业绩", "获批", "正式", "量产"]):
        catalyst, clabel = 15, "确定性"
    elif any(kw in summary for kw in ["或将", "预计", "接近", "计划", "推进", "验证"]):
        catalyst, clabel = 10, "高置信"
    elif any(kw in summary for kw in ["传", "据称", "关注", "跟踪", "预期"]):
        catalyst, clabel = 8, "跟踪"
    else:
        catalyst, clabel = 5, "跟踪"

    total = org + market + catalyst

    # 阶段判定
    if total >= 85: stage = "🔥主升"
    elif total >= 65: stage = "📈强化"
    elif total >= 50: stage = "➡️持续"
    else: stage = "🌱孵化"

    # 均价涨幅
    avg_pct = round(sum(pcts)/len(pcts), 1) if 'pcts' in dir() and pcts else 0

    return {
        "inst": org, "market": market, "catalyst": catalyst, "total": total,
        "avgPct": avg_pct, "catalystLabel": clabel,
    }, stage


# ============================================================
# 分类引擎 (README v2.1 简化版)
# ============================================================

def classify_stocks(stocks, stocks_with_reasons):
    """
    决策树分类: 按原文组序 + 标的数量
    简化版规则:
    - 1只 → 全部龙头
    - 2-5只 → 1龙头, 2-3弹性, 其余相关
    - 6+只 → 1龙头, 2-4弹性, 其余相关
    """
    leader, flex, related = [], [], []

    if len(stocks) == 1:
        leader = stocks[:]
    elif len(stocks) <= 5:
        leader = stocks[:1]
        flex = stocks[1:3]
        related = stocks[3:]
    else:
        leader = stocks[:1]
        flex = stocks[1:4]
        related = stocks[4:]

    return leader, flex, related


# ============================================================
# 摘要/引用提取 (README 规范)
# ============================================================

def extract_summary_quote(summary_raw):
    """提取摘要(≤85字)和引用(≤60字)"""
    if not summary_raw:
        return "", ""

    # 清理
    clean = re.sub(r'<[^>]+>', '', summary_raw)
    clean = re.sub(r'\*\*', '', clean).strip()

    # 移除"关注："之后的股票列表
    if "关注：" in clean:
        analysis = clean.split("关注：")[0].strip()
    elif "关注:" in clean:
        analysis = clean.split("关注:")[0].strip()
    else:
        analysis = clean

    # 移除时间/背景引导语
    analysis = re.sub(r'^在过去\d+小时内[，,]?\s*', '', analysis)
    analysis = re.sub(r'^\d+月\d+日[，,]?\s*', '', analysis)
    analysis = re.sub(r'^美国当地时间[^，,]*[，,]\s*', '', analysis)
    analysis = re.sub(r'^截至[^，,]*[，,]\s*', '', analysis)
    analysis = re.sub(r'^昨晚[^(]*[）)][，,]\s*', '', analysis)
    analysis = re.sub(r'^昨夜今晨[^(]*[）)][，,]\s*', '', analysis)
    analysis = re.sub(r'^本周[，,]?\s*', '', analysis)

    # 移除元论述
    analysis = re.sub(r'这一事件的边际变化在于[，,]?\s*', '', analysis)
    analysis = re.sub(r'这标志着[，,]?\s*', '', analysis)
    analysis = re.sub(r'此举意味着[，,]?\s*', '', analysis)

    # 取第一句做摘要 (≤85字)
    sentences = re.split(r'[。；;]', analysis)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if sentences:
        summary = sentences[0][:85]
        if len(sentences[0]) > 85 and not summary.endswith("。"):
            summary += "…"
    else:
        summary = analysis[:85]

    # 取第二句做引用 (≤60字)
    if len(sentences) >= 2:
        quote = sentences[1][:60]
    elif len(sentences) >= 1:
        quote = sentences[0][:60]
    else:
        quote = ""

    return summary, quote


# ============================================================
# 标的理由提取 (README: 照抄Alpha派原文)
# ============================================================

def build_stock_reasons(stocks_with_reasons):
    """从Alpha派原文提取每个标的的推荐理由"""
    reason_map = {}
    for sr in stocks_with_reasons:
        name = sr.get("name", "").strip()
        reason = sr.get("reason", "").strip()
        if name and reason:
            reason_map[name] = reason
    return reason_map


# ============================================================
# 东方财富实时行情
# ============================================================

def fetch_live_prices(secid_map):
    """通过curl拉取东财实时行情"""
    quotes = {}
    secids = list(set(secid_map.values()))
    for i in range(0, len(secids), 50):
        batch = secids[i:i+50]
        url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&fields=f2,f3,f4,f12,f14,f20&secids={','.join(batch)}"
        try:
            r = subprocess.run(["curl", "-s", "--connect-timeout", "8", "--max-time", "12", url],
                             capture_output=True, text=True, timeout=15)
            if r.returncode == 0 and r.stdout:
                data = json.loads(r.stdout)
                if data.get("data") and data["data"].get("diff"):
                    for d in data["data"]["diff"]:
                        quotes[d["f14"]] = {
                            "price": d.get("f2", 0),
                            "change_pct": d.get("f3", 0),
                            "code": d.get("f12", ""),
                            "pe": d.get("f20", 0),
                        }
        except Exception:
            pass
        _time.sleep(0.3)
    return quotes


# ============================================================
# 主构建函数: 生成 ED JSON
# ============================================================

def build_ed_json(edition, raw_topics, raw_opp, live_prices=None, date_str="2026-06-23"):
    """
    构建符合 README 规范的 ED JSON 数据块

    Args:
        edition: "mc"|"pm"|"ev"|"gv"
        raw_topics: Alpha派 topic list
        raw_opp: Alpha派 opportunity list
        live_prices: 东方财富实时行情 dict
        date_str: 日期字符串
    """
    live_prices = live_prices or {}

    edition_meta = {
        "mc": {"label": "晨会版", "icon": "🌅", "updateTime": f"{date_str} 07:05"},
        "pm": {"label": "午间版", "icon": "☀️", "updateTime": f"{date_str} 11:35"},
        "ev": {"label": "晚间版", "icon": "🌙", "updateTime": f"{date_str} 20:00"},
        "gv": {"label": "全球版", "icon": "🌍", "updateTime": f"{date_str} 08:03"},
    }
    meta = edition_meta.get(edition, edition_meta["mc"])

    # 收集所有标的 & secid映射
    all_stock_names = []
    for t in raw_topics:
        all_stock_names.extend(t.get("stocks", []))
    secid_map = {}
    for name in set(all_stock_names):
        sid = get_secid(name)
        if sid:
            secid_map[name] = sid

    # 构建主题列表
    topics = []
    for t in raw_topics:
        summary_raw = t.get("summary_raw", t.get("summary_clean", ""))
        stocks = t.get("stocks", [])
        stocks_with_reasons = t.get("stocks_with_reasons", [])

        # 评分
        scores, stage = score_topic_v3(t, live_prices)

        # 摘要/引用
        ai_summary, bp_quote = extract_summary_quote(summary_raw)

        # 分类
        reason_map = build_stock_reasons(stocks_with_reasons)
        leader_names, flex_names, related_names = classify_stocks(stocks, stocks_with_reasons)

        # 构建分组
        groups = []
        for label, names in [("龙头首选", leader_names), ("弹性机会", flex_names), ("相关标的", related_names)]:
            if not names:
                continue
            items = []
            for name in names:
                reason = reason_map.get(name, label)
                price_info = live_prices.get(name, {})
                price = price_info.get("price") if price_info.get("price") else None
                pct = price_info.get("change_pct") if price_info.get("change_pct") is not None else None
                pe = price_info.get("pe") if price_info.get("pe") else None
                items.append({
                    "name": name,
                    "reason": reason,
                    "price": price,
                    "pct": pct,
                    "pe": pe,
                    "marketCap": None,
                })
            groups.append({"label": label, "items": items})

        # 热度排序 (降序)
        topics.append({
            "topic": t["topic"],
            "heat": scores["total"],
            "stage": stage,
            "summary": ai_summary,
            "quote": bp_quote,
            "alphaIndex": t.get("heat", 5),
            "scores": scores,
            "groups": groups,
        })

    # 按热度排序
    topics.sort(key=lambda x: x["heat"], reverse=True)

    # 机会前瞻 (简化)
    opp_count = 0
    # 全球版或晨会版可能有
    if raw_opp:
        # 简化: 机会前瞻不生成主题卡片，只统计数量
        opp_topics = []
        for t in raw_opp:
            summary_raw = t.get("summary_raw", "")
            ai_summary, _ = extract_summary_quote(summary_raw)
            opp_stocks = []
            for sname in t.get("stocks", [])[:6]:
                sid = secid_map.get(sname, "")
                price_info = live_prices.get(sname, {})
                opp_stocks.append({
                    "name": sname,
                    "reason": "前瞻标的",
                    "price": price_info.get("price"),
                    "pct": price_info.get("change_pct"),
                    "pe": price_info.get("pe"),
                    "marketCap": None,
                })
            if opp_stocks:
                opp_topics.append({
                    "topic": t.get("topic", ""),
                    "summary": ai_summary,
                    "stocks": opp_stocks,
                    "scores": {"inst": 20, "market": 5, "catalyst": 5, "total": 30, "avgPct": 0, "catalystLabel": "跟踪"},
                })
        # 把机会前瞻追加到 topics 数组末尾
        if opp_topics:
            topics.extend(opp_topics)
            opp_count = len(opp_topics)

    # 一句话市场摘要
    top3_names = [t["topic"] for t in topics[:3]]
    avg_heat = sum(t["heat"] for t in topics[:3]) / min(3, len(topics)) if topics else 0
    if avg_heat >= 85:
        mood = "机构高度聚焦，市场情绪高涨"
    elif avg_heat >= 65:
        mood = "机构积极布局，结构性机会突出"
    else:
        mood = "市场轮动加速，关注主线清晰的方向"
    market_summary = f"今日聚焦：{'、'.join(top3_names)}。{mood}。"

    # 日期显示
    date_parts = date_str.split("-")
    date_display = f"{date_parts[0]}年{date_parts[1]}月{date_parts[2]}日"

    # 构建完整 ED JSON
    ed_json = {
        "edition": {
            "type": edition,
            "label": meta["label"],
            "date": date_str,
            "dateDisplay": date_display,
            "updateTime": meta["updateTime"],
        },
        "stats": {
            "topics": len(topics) - opp_count,
            "stocks": len(set(all_stock_names)),
            "opportunities": opp_count,
        },
        "marketSummary": market_summary,
        "topics": topics,
        "secidMap": secid_map,
    }

    return ed_json


# ============================================================
# 注入模板生成 HTML
# ============================================================

def inject_template(ed_json, output_path):
    """将 ED JSON 注入模板生成最终 HTML"""
    template = TEMPLATE.read_text(encoding="utf-8")
    json_str = json.dumps(ed_json, ensure_ascii=False, separators=(',', ':'))

    # 替换占位符
    html = template.replace("__ED_PLACEHOLDER__", json_str)

    # 更新 title
    ed = ed_json["edition"]
    new_title = f"蓝宝书Max · {ed['dateDisplay']} {ed['label']}"
    html = re.sub(r'<title>.*?</title>', f'<title>{new_title}</title>', html)

    # 写入
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"  ✅ {output_path} ({len(html)/1024:.1f} KB)")
    return html


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="蓝宝书Max 报告构建器")
    parser.add_argument("--edition", choices=["mc", "pm", "gv", "all"],
                        default="all", help="版本 (默认: all)")
    parser.add_argument("--no-live", action="store_true", help="不拉取实时行情")
    args = parser.parse_args()

    print("📖 解析 Alpha派 数据...")
    reports = parse_reports()
    print(f"   晨会版: {len(reports['am'])} 条")
    print(f"   全球版: {len(reports['global'])} 条")

    today = datetime.now(CST).strftime("%Y-%m-%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 晨会版
    if args.edition in ("mc", "all"):
        am_all = reports["am"]
        am_hot = [t for t in am_all if t["section"] == "市场热点"]
        am_opp = [t for t in am_all if t["section"] == "机会前瞻"]
        print(f"\n🌅 生成晨会版...")
        ed = build_ed_json("mc", am_hot, am_opp, date_str=today)
        inject_template(ed, str(OUTPUT_DIR / f"mc-{today.replace('-', '')}.html"))

    # 午间版
    if args.edition in ("pm", "all"):
        # 尝试读取真实午间版数据
        if MD_DATA_JSON.exists():
            print(f"\n☀️ 生成午间版（真实数据）...")
            try:
                md_data = json.load(open(MD_DATA_JSON))
                report = md_data.get("report", {})
                md_topics = []
                for section in report.get("contentJson", []):
                    for t in section.get("children", []):
                        stocks = re.findall(r'\*\*(.+?)\*\*', t.get("summary", ""))
                        stocks = [x for x in stocks if len(x) <= 12 and '/' not in x]
                        md_topics.append({
                            "section": section.get("title", "市场热点"),
                            "topic": t.get("topicName", ""),
                            "heat": t.get("index", 5),
                            "summary_raw": t.get("summary", ""),
                            "summary_clean": re.sub(r'<[^>]+>', '', t.get("summary", "")),
                            "stocks": stocks,
                            "stocks_with_reasons": _parse_stock_reasons(t.get("summary", "")),
                            "id": t.get("id", 0),
                        })
                md_hot = [t for t in md_topics if t["section"] == "市场热点"]

                # 拉取实时行情
                live_prices = {}
                if not args.no_live:
                    all_names = [s for t in md_hot for s in t["stocks"]]
                    secids = build_secid_map(all_names)
                    if secids:
                        live_prices = fetch_live_prices(secids)
                        print(f"    📊 实时行情: {len(live_prices)}/{len(secids)} 标的")

                ed = build_ed_json("pm", md_hot, [], live_prices, today)
                inject_template(ed, str(OUTPUT_DIR / f"pm-{today.replace('-', '')}.html"))
            except Exception as e:
                print(f"  ⚠️ 午间版生成失败: {e}")
                import traceback; traceback.print_exc()
        else:
            print(f"  ⚠️ 缺少午间版数据文件 {MD_DATA_JSON}，跳过")

    # 全球版
    if args.edition in ("gv", "all"):
        gv_all = reports["global"]
        gv_hot = [t for t in gv_all if t.get("section", "") in
                  ("市场热点", "隔夜美股复盘", "全球重点事件梳理", "美股复盘", "全球事件")]
        print(f"\n🌍 生成全球版...")
        ed = build_ed_json("gv", gv_hot, [], date_str=today)
        inject_template(ed, str(OUTPUT_DIR / f"gv-{today.replace('-', '')}.html"))

    print(f"\n🎉 全部完成!")
