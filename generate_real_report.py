#!/usr/bin/env python3
"""
蓝宝书Max · 从Alpha派真实数据生成报告 v5
评分算法：
  主题热度 = 机构关注度(0-40) + 市场确认度(0-35) + 催化质量(0-25)
  标的 Alpha = 产业链位势(0-30) + 弹性系数(0-30) + 筹码质量(0-40)
"""
import json, re, sys, time as _time
from pathlib import Path
from datetime import datetime

import requests as _requests

sys.path.insert(0, str(Path(__file__).parent))

from pipeline_v2 import generate_report_html, load_design_system, OUTPUT_DIR
from stock_secid import get_secid
from industry_chain import match_chain

REPORT_JSON = Path("data/reports_2026-06-23.json")
CST = __import__('datetime', fromlist=['timezone','timedelta']).timezone(__import__('datetime', fromlist=['timedelta']).timedelta(hours=8))

# ===== 评分引擎 =====

def score_topic(topic_data, alpha_index):
    """新评分算法：主题热度 = 机构关注(0-40) + 市场确认(0-35) + 催化质量(0-25)"""
    heat_raw = topic_data["heat"]  # Alpha派 1-10 原始热度

    # 机构关注度(0-40)：从原始热度+摘要长度推断
    summary_len = len(topic_data.get("summary_clean", ""))
    if heat_raw >= 9:
        org_attention = 34 + min(heat_raw - 9, 1) * 6  # 34-40
    elif heat_raw >= 7:
        org_attention = 24 + (heat_raw - 7) * 5  # 24-34
    elif heat_raw >= 5:
        org_attention = 14 + (heat_raw - 5) * 5  # 14-29
    else:
        org_attention = heat_raw * 3  # 0-15

    # 市场确认度(0-35)：摘要越长说明讨论越深入
    if summary_len > 400:
        market_confirm = 28 + min((summary_len - 400) / 200, 1) * 7
    elif summary_len > 200:
        market_confirm = 18 + (summary_len - 200) / 200 * 10
    else:
        market_confirm = max(5, summary_len / 200 * 13)

    market_confirm = int(min(market_confirm, 35))

    # 催化质量(0-25)：从摘要关键词判断事件可持续性
    summary = topic_data.get("summary_clean", "")
    catalyst_keywords = {
        "禁令": 22, "涨价": 20, "断供": 22, "制裁": 20, "管制": 18,
        "量产": 18, "业绩": 15, "订单": 17, "突破": 16, "政策": 16,
        "报告": 12, "预期": 13, "上调": 15, "超预期": 19,
    }
    catalyst_score = 8
    for kw, s in catalyst_keywords.items():
        if kw in summary:
            catalyst_score = max(catalyst_score, s)

    # 趋势判断
    if "持续" in summary or "强化" in summary:
        catalyst_score = min(catalyst_score + 2, 25)
    if "反转" in summary or "拐点" in summary:
        catalyst_score = min(catalyst_score + 3, 25)

    return {
        "org_attention": org_attention,
        "market_confirm": market_confirm,
        "catalyst_quality": int(catalyst_score),
        "heat_total": org_attention + market_confirm + int(catalyst_score),
    }


def score_stock(stock_name, chain_context, position_in_summary):
    """标的 Alpha 评分 = 产业链位势(0-30) + 弹性系数(0-30) + 筹码质量(0-40)"""

    # 产业链位势(0-30)：在链中位置 + 摘要位置
    if chain_context:
        chain_name = chain_context.get("name", "")
        is_upstream = any(k in chain_name for k in ["上游", "原料", "矿"])
        is_midstream = any(k in chain_name for k in ["中游", "芯片", "器件", "粉体"])
        is_downstream = any(k in chain_name for k in ["下游", "应用", "分销"])
        if is_upstream:
            chain_pos = 24
        elif is_midstream:
            chain_pos = 18
        elif is_downstream:
            chain_pos = 12
        else:
            chain_pos = 14
    else:
        chain_pos = 12

    # 摘要中提到顺序（越靠前越核心）
    pos_bonus = max(0, 6 - position_in_summary * 1.5) if position_in_summary < 4 else 0
    chain_pos = min(int(chain_pos + pos_bonus), 30)

    # 弹性系数(0-30)：小市值通常弹性更大
    small_cap_hints = ["股份", "科技", "材料", "光电", "新材"]
    mid_cap_hints = ["集团", "国际", "证券"]
    large_cap_hints = ["中国", "宁德", "美的", "中信"]

    if any(h in stock_name for h in small_cap_hints):
        elasticity = 22
    elif any(h in stock_name for h in large_cap_hints):
        elasticity = 10
    elif any(h in stock_name for h in mid_cap_hints):
        elasticity = 15
    else:
        elasticity = 16

    # 筹码质量(0-40)：有secid的A股基础分更高
    secid = get_secid(stock_name)
    if secid:
        chip_quality = 28
    else:
        chip_quality = 8

    # 价格弹性暗示（技术类股票通常有更高beta）
    tech_hints = ["科技", "光电", "激光", "半导体", "芯片", "存储", "智能"]
    if any(h in stock_name for h in tech_hints):
        elasticity = min(elasticity + 6, 30)
        chip_quality = max(chip_quality - 4, 0)

    return {
        "chain_position": chain_pos,
        "elasticity": elasticity,
        "chip_quality": chip_quality,
        "alpha_total": chain_pos + elasticity + chip_quality,
        "secid": secid,
    }


def fetch_realtime_quotes(secid_map):
    """从东方财富API拉取所有标的的实时行情（服务端调用，午间版用）"""
    if not secid_map:
        return {}

    secids = list(set(secid_map.values()))
    quotes = {}
    sess = _requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    })

    for i in range(0, len(secids), 50):
        batch = secids[i:i + 50]
        try:
            params = {
                "fltt": "2",
                "fields": "f2,f3,f4,f12,f14",
                "secids": ",".join(batch),
                "_": str(int(_time.time() * 1000)),
            }
            resp = sess.get(
                "https://push2.eastmoney.com/api/qt/ulist.np/get",
                params=params, timeout=10
            )
            data = resp.json()
            if data.get("data") and data["data"].get("diff"):
                for item in data["data"]["diff"]:
                    name = item.get("f14", "")
                    quotes[name] = {
                        "price": item.get("f2"),
                        "change_pct": item.get("f3") or 0,
                        "code": item.get("f12", ""),
                    }
        except Exception as e:
            print(f"  ⚠️ 实时行情批量拉取异常: {e}")

    print(f"  📊 实时行情: 拉取 {len(secids)} 个标的，成功 {len(quotes)} 个")
    return quotes


def build_secid_map(stock_names):
    """从标的名列表构建secid映射"""
    used = {}
    for name in stock_names:
        sid = get_secid(name)
        if sid:
            used[name] = sid
    return used


# ===== 数据解析 =====

def parse_reports():
    with open(REPORT_JSON) as f:
        data = json.load(f)

    output = {"am": [], "global": []}
    for r in data:
        title = r["title"]
        if "晨会版" in title:
            key = "am"
        elif "全球版" in title:
            key = "global"
        else:
            continue
        if output[key]:
            continue

        for s in r.get("contentJson", []):
            for t in s.get("children", []):
                stocks = re.findall(r'\*\*(.+?)\*\*', t.get("summary", ""))
                stocks = [x for x in stocks if len(x) <= 12 and '/' not in x and '%' not in x[0]]
                clean = re.sub(r'<[^>]+>', '', t["summary"])
                clean = re.sub(r'\*\*', '', clean)

                output[key].append({
                    "section": s["title"],
                    "topic": t["topicName"],
                    "heat": t.get("index", 5),
                    "summary_raw": t.get("summary", ""),
                    "summary_clean": clean,
                    "stocks": stocks,
                    "id": t.get("id", 0),
                })
    return output


def format_topic_for_pipeline(topic, rank, all_secids):
    """格式化主题 + 新评分算法"""
    scores = score_topic(topic, rank)

    heat = scores["heat_total"]
    if heat >= 85:
        state = "主升"
    elif heat >= 65:
        state = "强化"
    elif heat >= 45:
        state = "持续"
    else:
        state = "孵化"

    # 标的分层
    stocks_data = []
    stocks = topic.get("stocks", [])
    if stocks:
        leader_items, flex_items, rest_items = [], [], []
        for i, sname in enumerate(stocks):
            stock_alpha = score_stock(sname, None, i)
            sid = all_secids.get(sname, "")
            item = {
                "name": sname, "code": sid,
                "reason": "核心标的" if i < 2 else ("弹性标的" if i < 4 else "相关标的"),
                "alpha": stock_alpha["alpha_total"],
                "change_pct": 0,
            }
            if i < 2:
                leader_items.append(item)
            elif i < 4:
                flex_items.append(item)
            else:
                rest_items.append(item)

        if leader_items:
            stocks_data.append({"tier": "龙头首选", "label": "龙头首选", "items": leader_items})
        if flex_items:
            stocks_data.append({"tier": "弹性机会", "label": "弹性机会", "items": flex_items})
        if rest_items:
            stocks_data.append({"tier": "相关标的", "label": "相关标的", "items": rest_items})

    return {
        "title": topic["topic"],
        "summary": topic["summary_clean"][:120],
        "bluebook_quote": topic["summary_clean"][:200],
        "heat": heat,
        "state": state,
        "org_attention": scores["org_attention"],
        "market_confirm": scores["market_confirm"],
        "catalyst_quality": scores["catalyst_quality"],
        "stocks": stocks_data,
    }


# ===== 报告生成 =====

def make_sentiment(topics_heat, version):
    avg = sum(topics_heat) / len(topics_heat) if topics_heat else 50
    if avg >= 75:
        signal, cls = "强势做多", "signal-bullish"
    elif avg >= 60:
        signal, cls = "积极看多", "signal-bullish"
    elif avg >= 45:
        signal, cls = "结构性轮动", "signal-neutral"
    else:
        signal, cls = "谨慎观望", "signal-neutral"

    top3 = sorted(topics_heat, reverse=True)[:3]
    if version == "global":
        return f"全球市场聚焦：AI算力与存储板块持续走强，市场情绪{signal}", signal
    return f"最强方向聚焦今日热点，机构密集覆盖{len(topics_heat)}个方向，市场情绪{signal}", signal


def generate_all():
    print("📖 解析 Alpha派 真实数据...")
    reports = parse_reports()
    print(f"   晨会版: {len(reports['am'])} 条")
    print(f"   全球版: {len(reports['global'])} 条")

    css = load_design_system()
    today = datetime.now(CST).strftime("%Y-%m-%d")
    date_display = "2026年06月23日"

    # ---- 晨会版 ----
    am_all = reports["am"]
    am_hot = [t for t in am_all if t["section"] == "市场热点"]
    am_opp = [t for t in am_all if t["section"] == "机会前瞻"]

    # 收集所有标的为secid
    all_stocks = []
    for t in am_all:
        all_stocks.extend(t.get("stocks", []))
    secids = build_secid_map(all_stocks)

    am_formatted = [format_topic_for_pipeline(t, i+1, secids) for i, t in enumerate(am_hot)]

    # Alpha精选 TOP5
    alpha_top5 = []
    sorted_by_heat = sorted(am_formatted, key=lambda x: x["heat"], reverse=True)
    for f in sorted_by_heat[:5]:
        first_tier = f["stocks"][0] if f["stocks"] else None
        first_item = first_tier["items"][0] if first_tier else None
        if first_item:
            alpha_top5.append({
                "name": first_item["name"], "code": first_item["code"],
                "alpha": f["heat"], "reason": f["title"][:30],
                "change_pct": 0,
            })

    sentiment, signal = make_sentiment([t["heat"] for t in am_formatted], "am")

    am_stats = {
        "total_topics": len(am_formatted),
        "total_stocks": len(all_stocks),
        "total_opportunities": len(am_opp),
        "market_signal": signal,
        "summary": sentiment,
        "alpha_top5": alpha_top5,
        "opportunities": [
            {"title": t["topic"], "summary": t["summary_clean"][:100], "bluebook_quote": t["summary_clean"][:200]}
            for t in am_opp
        ],
        "secid_map": {k: v for k, v in secids.items()},
    }

    html = generate_report_html(
        title=f"蓝宝书 · {date_display} 晨会版",
        date_str=date_display, version="am",
        topics=am_formatted, statistics=am_stats, design_css=css,
    )

    reports_dir = OUTPUT_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "am-20260623.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ 晨会版: {path} ({len(html)/1024:.1f} KB, {len(am_formatted)} 主题, {len(secids)} 标的有实时行情)")

    # ---- 全球版 ----
    global_all = reports["global"]
    us_topics = [t for t in global_all if "美股" in t["section"] or "复盘" in t["section"]]
    global_events = [t for t in global_all if "全球" in t["section"] or "事件" in t["section"]]

    # 全球版美股标的不用A股secid
    global_formatted = [format_topic_for_pipeline(t, i+1, secids) for i, t in enumerate(global_all)]
    g_sentiment, g_signal = make_sentiment([t["heat"] for t in global_formatted], "global")

    g_stats = {
        "total_topics": len(global_formatted),
        "total_stocks": sum(len(t.get("stocks", [])) for t in global_all),
        "total_opportunities": len(global_events),
        "market_signal": g_signal,
        "summary": g_sentiment,
        "alpha_top5": [],
        "opportunities": [
            {"title": t["topic"], "summary": t["summary_clean"][:100], "bluebook_quote": t["summary_clean"][:200]}
            for t in global_events
        ],
        "secid_map": {},
    }

    g_html = generate_report_html(
        title=f"蓝宝书 · {date_display} 全球版",
        date_str=date_display, version="global",
        topics=global_formatted, statistics=g_stats, design_css=css,
    )

    g_path = reports_dir / "global-20260623.html"
    with open(g_path, "w", encoding="utf-8") as f:
        f.write(g_html)
    print(f"  ✅ 全球版: {g_path} ({len(g_html)/1024:.1f} KB, {len(global_formatted)} 主题)")

    # ---- 午间版（真实午盘行情版） ----
    print("\n☀️  生成午间版（拉取实时行情）...")
    ds = datetime.now(CST)

    # 拉取所有标的的实时行情
    realtime_quotes = fetch_realtime_quotes(secids)

    # 选取热度最高的8个主题
    noon_topics_raw = sorted(am_formatted, key=lambda x: x["heat"], reverse=True)[:8]

    # 深度拷贝午间topic并注入真实涨跌幅
    import copy
    noon_topics = copy.deepcopy(noon_topics_raw)

    # 收集所有午间标的数据用于分析
    all_noon_stocks = []  # {name, change_pct, topic_title}

    for t in noon_topics:
        topic_title = t["title"]
        stocks_data = t.get("stocks", [])

        # 计算该主题标的的平均涨跌幅
        topic_changes = []

        for tier_data in stocks_data:
            items = tier_data.get("items", [])
            for item in items:
                name = item.get("name", "")
                rt = realtime_quotes.get(name, {})
                real_chg = rt.get("change_pct", 0)
                if real_chg is None:
                    real_chg = 0
                item["change_pct"] = real_chg
                topic_changes.append(real_chg)
                all_noon_stocks.append({
                    "name": name, "change_pct": real_chg,
                    "topic": topic_title,
                })

            # 按实际涨跌幅重新排序（涨多的在前）
            items.sort(key=lambda x: x.get("change_pct", 0) or 0, reverse=True)

        # 根据该主题真实涨跌幅重写摘要
        avg_chg = sum(topic_changes) / len(topic_changes) if topic_changes else 0
        up_count = sum(1 for c in topic_changes if c > 0) if topic_changes else 0
        down_count = sum(1 for c in topic_changes if c < 0) if topic_changes else 0
        total = len(topic_changes)

        # 找该主题表现最好的3个标的
        best = sorted(all_noon_stocks[-total:] if total > 0 else [],
                       key=lambda x: x.get("change_pct", 0) or 0, reverse=True)[:3]
        best_names = "、".join([b["name"] for b in best]) if best else ""

        if up_count > total * 0.6:
            noon_summary = f"午盘该方向持续走强，{total}只标的中{up_count}只上涨"
            if best_names:
                noon_summary += f"，{best_names}领涨"
        elif up_count > down_count:
            noon_summary = f"午盘该方向分化上行，{up_count}只上涨/{down_count}只回调"
            if best_names:
                noon_summary += f"，{best_names}表现突出"
        elif down_count > up_count:
            noon_summary = f"午盘该方向整体承压，{down_count}只回调/{up_count}只翻红"
            if best_names:
                noon_summary += f"，仅{best_names}逆势走强"
        else:
            noon_summary = f"午盘该方向横盘整理，涨跌互现"

        noon_summary += f"，平均涨跌幅{avg_chg:+.2f}%。{t.get('summary','')[:60]}"
        t["summary"] = noon_summary

    # Alpha精选TOP5：基于真实涨幅重新排序
    noon_stocks_sorted = sorted(all_noon_stocks, key=lambda x: x.get("change_pct", 0) or 0, reverse=True)
    noon_alpha = []
    seen_alpha = set()
    for s in noon_stocks_sorted:
        if s["name"] in seen_alpha:
            continue
        seen_alpha.add(s["name"])
        sid = secids.get(s["name"], "")
        noon_alpha.append({
            "name": s["name"], "code": sid,
            "alpha": int(abs(s.get("change_pct", 0)) * 10) + 60,
            "reason": s["topic"][:30],
            "change_pct": s.get("change_pct", 0),
        })
        if len(noon_alpha) >= 5:
            break

    # 午间机会前瞻：找涨幅最大的板块和异动标的
    # 按主题聚合涨幅
    topic_perf = {}
    for s in all_noon_stocks:
        t = s["topic"]
        if t not in topic_perf:
            topic_perf[t] = []
        topic_perf[t].append(s)

    noon_opportunities = []
    # 找平均涨幅最高的板块
    topic_ranks = []
    for tname, stocks in topic_perf.items():
        avg = sum(s["change_pct"] for s in stocks) / len(stocks) if stocks else 0
        topic_ranks.append((tname, avg, stocks))
    topic_ranks.sort(key=lambda x: x[1], reverse=True)

    if topic_ranks:
        top_topic = topic_ranks[0]
        top_stocks = sorted(top_topic[2], key=lambda x: x["change_pct"] or 0, reverse=True)[:3]
        top_names = "、".join([s["name"] for s in top_stocks])
        noon_opportunities.append({
            "title": f"午盘领涨方向：{top_topic[0][:20]}",
            "summary": f"早盘该方向整体走强，板块平均涨幅{top_topic[1]:+.2f}%，{top_names}等标的领涨。关注午后能否延续强势。",
            "bluebook_quote": f"早盘{top_topic[0][:15]}方向资金明显流入，{top_names}涨幅居前，午后关注量能是否持续。",
        })

    if len(topic_ranks) > 1:
        second_topic = topic_ranks[1]
        second_stocks = sorted(second_topic[2], key=lambda x: x["change_pct"] or 0, reverse=True)[:2]
        second_names = "、".join([s["name"] for s in second_stocks])
        noon_opportunities.append({
            "title": f"午盘异动关注：{second_topic[0][:20]}",
            "summary": f"该方向同步走强，{second_names}涨幅居前。午盘情绪若能延续，午后或有进一步表现。",
            "bluebook_quote": f"{second_topic[0][:15]}方向在早盘获得资金关注，{second_names}等标的异动明显，值得午后跟踪。",
        })

    # 如果只有1个机会，补充一个
    if len(noon_opportunities) < 2:
        noon_opportunities.append({
            "title": "午盘观察：关注午后量能变化",
            "summary": "早盘多个方向轮动活跃，午后关注成交量能否持续放大，决定反弹持续性。",
            "bluebook_quote": "午盘量能是判断当日行情持续性的关键指标，关注成交额能否突破早盘峰值。",
        })

    # 午间市场情绪
    all_changes = [s["change_pct"] for s in all_noon_stocks if s.get("change_pct") is not None]
    noon_avg_chg = sum(all_changes) / len(all_changes) if all_changes else 0
    noon_up_ratio = sum(1 for c in all_changes if c > 0) / len(all_changes) if all_changes else 0

    if noon_up_ratio > 0.65:
        noon_signal = "强势做多"
        noon_sig_cls = "signal-bullish"
    elif noon_up_ratio > 0.45:
        noon_signal = "积极看多"
        noon_sig_cls = "signal-bullish"
    elif noon_up_ratio > 0.30:
        noon_signal = "结构性轮动"
        noon_sig_cls = "signal-neutral"
    else:
        noon_signal = "谨慎观望"
        noon_sig_cls = "signal-neutral"

    noon_sentiment = (
        f"午盘概览：覆盖{len(all_noon_stocks)}只标的，{int(noon_up_ratio*100)}%上涨"
        f"，平均涨跌幅{noon_avg_chg:+.2f}%。"
        + (f"早盘情绪{noon_signal}，最强方向为{noon_opportunities[0]['title'].split('：')[1] if noon_opportunities else 'AI算力'}。"
           if noon_opportunities else "")
    )

    noon_secids_map = {k: v for k, v in secids.items()}
    noon_stats = {
        "total_topics": len(noon_topics),
        "total_stocks": len(all_noon_stocks),
        "total_opportunities": len(noon_opportunities),
        "market_signal": noon_signal,
        "summary": noon_sentiment,
        "alpha_top5": noon_alpha,
        "opportunities": noon_opportunities,
        "secid_map": noon_secids_map,
    }

    noon_html = generate_report_html(
        title=f"蓝宝书 · {date_display} 午间版",
        date_str=date_display, version="noon",
        topics=noon_topics, statistics=noon_stats, design_css=css,
    )

    noon_path = reports_dir / "md-20260623.html"
    with open(noon_path, "w", encoding="utf-8") as f:
        f.write(noon_html)
    realtime_count = len([s for s in all_noon_stocks if s.get("change_pct", 0) != 0])
    print(f"  ✅ 午间版: {noon_path} ({len(noon_html)/1024:.1f} KB, {len(noon_topics)} 主题, {realtime_count}/{len(all_noon_stocks)} 只标的有实时行情)")

    print(f"\n🎉 三份报告全部生成！")
    print(f"   📊 评分算法: 热度=机构{len([t for t in am_formatted if t.get('org_attention',0)>30])}条高机构关注 | 共{len(secids)}个标的有实时行情")


if __name__ == "__main__":
    generate_all()
