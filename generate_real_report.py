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

# ===== 评分引擎 v2 =====

def score_topic(topic_data, alpha_index, live_quotes=None):
    """
    三层独立评分:
      机构关注度(0-60): Alpha派 index → index/10 × 60
      市场信号(0-25):   标的平均涨跌幅绝对值
      催化强度(0-15):   摘要关键词推断
    总分 = 机构 + 市场 + 催化 (0-100)
    """
    heat_raw = topic_data["heat"]  # Alpha派 index (1-10)

    # === 第一层: 机构关注度 (0-60) ===
    org_attention = int(heat_raw / 10 * 60)

    # === 第二层: 市场信号 (0-25) ===
    market_signal = 5  # 默认: 无行情数据
    if live_quotes:
        stocks_data = topic_data.get("stocks_data", [])
        if not stocks_data:
            # 从 stocks_with_reasons 获取标的列表
            stocks_data = [sr["name"] for sr in topic_data.get("stocks_with_reasons", [])]
        if stocks_data:
            pcts = []
            for name in stocks_data:
                if name in live_quotes:
                    pct = live_quotes[name].get("change_pct", 0)
                    if isinstance(pct, (int, float)):
                        pcts.append(abs(pct))
            if pcts:
                avg_pct = sum(pcts) / len(pcts)
                if avg_pct >= 5:
                    market_signal = 25
                elif avg_pct >= 3:
                    market_signal = 18
                elif avg_pct >= 1:
                    market_signal = 10
                else:
                    market_signal = 5

    # === 第三层: 催化强度 (0-15) ===
    summary = topic_data.get("summary_clean", topic_data.get("summary_raw", ""))
    # 一级关键词: 确定性催化剂 (15分)
    if any(kw in summary for kw in ["官宣", "确认", "正式发布", "Q2业绩", "获批", "敲定"]):
        catalyst = 15
    # 二级: 高置信度预期 (10分)
    elif any(kw in summary for kw in ["或将", "预计", "接近", "计划量产", "涨价函", "上调"]):
        catalyst = 10
    # 三级: 传闻/跟踪 (5分)
    elif any(kw in summary for kw in ["传 ", "传\"", "据称", "关注", "跟踪"]):
        catalyst = 5
    else:
        catalyst = 5

    return {
        "org_attention": org_attention,
        "market_signal": market_signal,
        "catalyst": catalyst,
        "heat_total": org_attention + market_signal + catalyst,
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
    """从东方财富API拉取所有标的的实时行情（优先用curl，requests常被代理拦截）"""
    if not secid_map:
        return {}

    import subprocess
    secids = list(set(secid_map.values()))
    quotes = {}

    for i in range(0, len(secids), 50):
        batch = secids[i:i + 50]
        secid_str = ",".join(batch)
        url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&fields=f2,f3,f4,f12,f14&secids={secid_str}"

        try:
            result = subprocess.run(
                ["curl", "-s", "--connect-timeout", "10", "--max-time", "15", url],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                if data.get("data") and data["data"].get("diff"):
                    for item in data["data"]["diff"]:
                        name = item.get("f14", "")
                        quotes[name] = {
                            "price": item.get("f2"),
                            "change_pct": item.get("f3") or 0,
                            "code": item.get("f12", ""),
                        }
            _time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️ 实时行情拉取异常: {e}")

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

def _parse_stock_reasons(summary: str) -> list:
    """
    从 Alpha派摘要中提取股票和推荐理由
    模式: **name1**/**name2**（理由），**name3**（理由）
    """
    stocks = []
    if "关注：" in summary:
        stock_section = summary.split("关注：", 1)[1]
    elif "关注:" in summary:
        stock_section = summary.split("关注:", 1)[1]
    else:
        return stocks

    groups = re.split(r'[，,；;]', stock_section)
    for group in groups:
        group = group.strip()
        if not group:
            continue
        reason_match = re.search(r'[（(](.+?)[）)]', group)
        reason = reason_match.group(1).strip() if reason_match else ""
        names = re.findall(r'\*\*(.+?)\*\*', group)
        for name in names:
            name = name.strip()
            if len(name) > 12 or '/' in name:
                continue
            stocks.append({"name": name, "reason": reason})
    return stocks


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

                # 从摘要中解析股票推荐理由
                stocks_with_reasons = _parse_stock_reasons(t.get("summary", ""))

                output[key].append({
                    "section": s["title"],
                    "topic": t["topicName"],
                    "heat": t.get("index", 5),
                    "summary_raw": t.get("summary", ""),
                    "summary_clean": clean,
                    "stocks": stocks,
                    "stocks_with_reasons": stocks_with_reasons,  # 新增
                    "id": t.get("id", 0),
                })
    return output


def format_topic_for_pipeline(topic, rank, all_secids, live_quotes=None):
    """格式化主题 + 三层独立评分 + 决策树分类"""
    scores = score_topic(topic, rank, live_quotes)

    heat = scores["heat_total"]
    if heat >= 75:
        state = "主升"
    elif heat >= 55:
        state = "强化"
    elif heat >= 35:
        state = "持续"
    else:
        state = "孵化"

    # ===== 决策树分类: 龙头/弹性/相关 =====
    stocks = topic.get("stocks", [])
    reason_map = {}
    # 按 Alpha派原文 "关注：" 段落的自然分组
    stocks_with_reasons = topic.get("stocks_with_reasons", [])
    # 构建分组: 同一 reason 的标的 → 一组，顺序保持原文出现顺序
    groups = []  # [(reason, [stock_name, ...])]
    seen_groups = {}
    for sr in stocks_with_reasons:
        name = sr.get("name", "")
        reason = sr.get("reason", "").strip()
        if not reason:
            reason = "_default"
        if name and name not in reason_map:
            reason_map[name] = reason
        if reason not in seen_groups:
            seen_groups[reason] = len(groups)
            groups.append((reason, []))
        groups[seen_groups[reason]][1].append(name)

    # 决策树判定每组标的
    group_tiers = {}  # name → "龙头首选"|"弹性机会"|"相关标的"
    for gi, (reason, group_stocks) in enumerate(groups):
        first_of_group = group_stocks[0] if group_stocks else ""
        if gi == 0:
            # 第一组: 首位=龙头，其余=弹性
            group_tiers[first_of_group] = "龙头首选"
            for s in group_stocks[1:]:
                group_tiers[s] = "弹性机会"
        elif gi == 1:
            # 第二组: 角色含"核心"→弹性，否则→相关
            tier = "弹性机会" if "核心" in reason else "相关标的"
            for s in group_stocks:
                group_tiers[s] = tier
        else:
            # 第三组及以后: 全部相关
            for s in group_stocks:
                group_tiers[s] = "相关标的"

    # 不在任何分组的标的（只有名字没有角色描述）→ 按出现位置 fallback
    for i, sname in enumerate(stocks):
        if sname not in group_tiers:
            if i == 0:
                group_tiers[sname] = "龙头首选"
            elif i < 3:
                group_tiers[sname] = "弹性机会"
            else:
                group_tiers[sname] = "相关标的"

    # 构建三层分组数据
    leader_items, flex_items, rest_items = [], [], []
    for i, sname in enumerate(stocks):
        stock_alpha = score_stock(sname, None, i)
        sid = all_secids.get(sname, "")
        reason = reason_map.get(sname, "")
        if not reason:
            reason = "核心标的" if i < 2 else ("弹性标的" if i < 4 else "相关标的")
        tier = group_tiers.get(sname, "相关标的")
        item = {
            "name": sname, "code": sid,
            "reason": reason,
            "alpha": stock_alpha["alpha_total"],
            "change_pct": 0,
        }
        if tier == "龙头首选":
            leader_items.append(item)
        elif tier == "弹性机会":
            flex_items.append(item)
        else:
            rest_items.append(item)

    stocks_data = []
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
        "summary_raw": topic.get("summary_raw", topic.get("summary_clean", "")),
        "heat": heat,
        "state": state,
        "org_attention": scores["org_attention"],
        "market_confirm": scores["market_signal"],
        "catalyst_quality": scores["catalyst"],
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
