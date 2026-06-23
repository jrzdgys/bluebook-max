#!/usr/bin/env python3
"""
蓝宝书Max v3 · 全自动报告生成管道
整合: Alpha派数据解析 → 评分引擎 → 东方财富实时行情 → render_engine 渲染 → HTML
完全数据驱动，零硬编码

v3.1 更新:
  - 午间版使用真实Alpha派午间版数据（不再复用晨会版）
  - 📌精简为AI总结（1-2句），📘精简为蓝宝书重点（核心逻辑）
  - 股票推荐理由直接从Alpha派数据照抄
  - Alpha全量精简为Top20
  - 每个主题附带产业链分析
"""
import json, re, sys, time as _time
from pathlib import Path
from datetime import datetime
from collections import OrderedDict

import requests as _requests

sys.path.insert(0, str(Path(__file__).parent))

from render_engine import generate_report
from stock_secid import get_secid
from generate_real_report import (
    score_topic, score_stock, fetch_realtime_quotes,
    build_secid_map, parse_reports, make_sentiment,
    format_topic_for_pipeline,
)
from industry_chain import match_chain, CHAIN_DB

REPORT_JSON = Path("data/reports_2026-06-23.json")
MD_DATA_JSON = Path("data/md_complete_data.json")
OUTPUT_DIR = Path("output")
CST = __import__('datetime', fromlist=['timezone', 'timedelta']).timezone(
    __import__('datetime', fromlist=['timedelta']).timedelta(hours=8)
)

TIER_MAP = {"龙头首选": 1, "弹性机会": 2, "相关标的": 3}
MAX_ALPHA_DISPLAY = 20  # 全量Alpha精简显示


# ============================================================
# 午间版数据解析
# ============================================================

def parse_midday_data():
    """从 md_complete_data.json 解析真实午间版数据"""
    if not MD_DATA_JSON.exists():
        print("  ⚠️ md_complete_data.json 不存在，使用晨会版数据作为午间版")
        return None

    data = json.load(open(MD_DATA_JSON))
    report = data.get("report", {})
    topics = []

    for section in report.get("contentJson", []):
        section_name = section.get("title", "市场热点")
        for t in section.get("children", []):
            summary = t.get("summary", "")

            # 解析股票和推荐理由
            stocks_with_reasons = _parse_stock_reasons(summary)

            # 清理摘要
            clean = re.sub(r'<[^>]+>', '', summary)
            clean = re.sub(r'\*\*', '', clean)

            stock_names = [s["name"] for s in stocks_with_reasons]

            topics.append({
                "section": section_name,
                "topic": t.get("topicName", ""),
                "heat": t.get("index", 5),
                "summary_raw": summary,
                "summary_clean": clean,
                "stocks": stock_names,
                "stocks_with_reasons": stocks_with_reasons,  # 新字段
                "id": t.get("id", 0),
            })

    print(f"  ✅ 午间版: {len(topics)} 条主题")
    return topics


def _parse_stock_reasons(summary: str) -> list:
    """
    从 Alpha派摘要中提取股票和推荐理由
    模式: **name1**/**name2**（理由），**name3**（理由）
    """
    stocks = []
    # 分离"关注："之后的部分
    if "关注：" in summary:
        stock_section = summary.split("关注：", 1)[1]
    elif "关注:" in summary:
        stock_section = summary.split("关注:", 1)[1]
    else:
        return stocks

    # 按中文逗号/分号分组
    groups = re.split(r'[，,；;]', stock_section)
    for group in groups:
        group = group.strip()
        if not group:
            continue

        # 提取理由（中文括号或英文括号）
        reason_match = re.search(r'[（(](.+?)[）)]', group)
        reason = reason_match.group(1).strip() if reason_match else ""

        # 提取股票名
        names = re.findall(r'\*\*(.+?)\*\*', group)
        if not names and reason:
            # 没有粗体但可能有纯文本名字，跳过
            continue

        for name in names:
            name = name.strip()
            if len(name) > 12 or '/' in name:
                continue
            stocks.append({"name": name, "reason": reason})

    return stocks


# ============================================================
# 内容拆分优化
# ============================================================

def _split_summary_v2(raw_summary: str):
    """
    v2 拆分逻辑:
    - 📌 AI总结: 前1-2句（事件+边际变化）
    - 📘 蓝宝书重点: 投资逻辑句（"标志着"、"投资逻辑"、"核心"等关键句）
    """
    # 清理 HTML 和 Markdown
    clean = re.sub(r'<[^>]+>', '', raw_summary)
    clean = re.sub(r'\*\*', '', clean).strip()

    # 移除"关注："之后的部分（股票推荐）
    if "关注：" in clean:
        analysis_part = clean.split("关注：")[0].strip()
    elif "关注:" in clean:
        analysis_part = clean.split("关注:")[0].strip()
    else:
        analysis_part = clean

    # 按句号拆分句子
    sentences = re.split(r'[。；;]', analysis_part)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if not sentences:
        return clean[:120], ""

    # 📌 AI总结: 前1句（事件描述），max 80字
    ai_parts = []
    ai_len = 0
    for s in sentences[:2]:
        short_s = s[:80] if len(s) > 80 else s
        if ai_len + len(short_s) < 80:
            ai_parts.append(short_s)
            ai_len += len(short_s)
        else:
            break
    ai_summary = "。".join(ai_parts)
    if ai_summary and not ai_summary.endswith("。"):
        ai_summary += "。"
    if not ai_summary:
        ai_summary = analysis_part[:80] + "..."

    # 📘 蓝宝书重点: 核心逻辑句，max 60字
    key_markers = ["标志着", "投资逻辑", "核心边际", "市场正交易",
                   "这一变化", "预期将从", "逻辑已从"]
    bluebook_quote = ""
    for s in sentences:
        if any(m in s for m in key_markers):
            bluebook_quote = s[:60] if len(s) > 60 else s
            break

    if not bluebook_quote:
        # 取第二句（跳过纯事件描述），max 50字
        for s in sentences[1:]:
            if len(s) > 10:
                bluebook_quote = s[:50] if len(s) > 50 else s
                break

    return ai_summary.strip(), bluebook_quote.strip()


# ============================================================
# 产业链解析
# ============================================================

def get_industry_chain(topic_title: str, topic_stocks: list) -> dict:
    """
    为主题匹配产业链结构
    返回: {name, key_driver, nodes: [{level, role, stocks}]}
    """
    chain = match_chain(topic_title)
    if not chain:
        return None

    result = {
        "name": chain.name,
        "key_driver": chain.key_driver,
        "nodes": []
    }

    for node in chain.nodes:
        node_stocks = []
        for s in node.stocks:
            # 只保留在主题推荐列表中的标的
            if s["name"] in topic_stocks:
                node_stocks.append({
                    "name": s["name"],
                    "catalyst": s.get("catalyst", ""),
                    "code": s.get("code", ""),
                })
        result["nodes"].append({
            "level": node.name,
            "role": node.role,
            "stocks": node_stocks,
        })

    # 如果匹配的链中标的太少，返回 None
    total_matched = sum(len(n["stocks"]) for n in result["nodes"])
    if total_matched < 2:
        return None

    return result


# ============================================================
# 数据转换：old pipeline format → new render_engine format
# ============================================================

def topic_to_v3(topic: dict, rank: int, secids: dict, live_quotes: dict = None,
                mid_reasons: list = None) -> dict:
    """将 topic 转换为 render_engine 格式，产业链驱动"""
    live_quotes = live_quotes or {}

    # 📌📘 内容拆分（精简）
    summary_raw = topic.get("summary_raw", "")
    ai_summary, bluebook_quote = _split_summary_v2(summary_raw)

    # 构建理由映射
    reason_map = {}
    if mid_reasons:
        for sr in mid_reasons:
            name = sr["name"]
            reason = sr.get("reason", "")
            if name and name not in reason_map:
                reason_map[name] = reason

    # 降平所有标的（不再分层）
    all_stocks = []
    for tier_group in topic.get("stocks", []):
        items = tier_group.get("items", [])
        for item in items:
            name = item.get("name", "")
            code = item.get("code", "")
            pct = item.get("change_pct", 0)

            if name in live_quotes:
                q = live_quotes[name]
                pct_raw = q.get("change_pct", 0)
                if isinstance(pct_raw, (int, float)):
                    pct = pct_raw
                if not code and q.get("code"):
                    code = q["code"]

            reason = reason_map.get(name, "") or item.get("reason", "")

            all_stocks.append({
                "name": name, "code": code, "pct": pct, "reason": reason,
            })

    # 产业链分组
    all_names = [s["name"] for s in all_stocks]
    chain = get_industry_chain(topic.get("title", ""), all_names)
    chain_groups = _build_chain_groups(all_stocks, chain)

    return {
        "rank": rank,
        "title": topic["title"],
        "stage": topic.get("state", "持续"),
        "heat": topic["heat"],
        "heat_breakdown": {
            "机构关注度": topic.get("org_attention", 0),
            "市场确认度": topic.get("market_confirm", 0),
            "催化质量": topic.get("catalyst_quality", 0),
        },
        "ai_summary": ai_summary,
        "bluebook_quote": bluebook_quote,
        "chain_groups": chain_groups,
        "industry_chain": chain,
    }


def _build_chain_groups(all_stocks: list, chain: dict) -> list:
    """
    构建产业链分组：优先匹配数据库链，否则按理由自动推导
    返回: [{level: "上游"|"中游"|"下游", role: "...", stocks: [...]}]
    """
    if not all_stocks:
        return []

    # 尝试用数据库链分组
    if chain and chain.get("nodes"):
        groups = []
        node_order = []  # 记录节点顺序
        for node in chain["nodes"]:
            node_stocks = []
            for ns in node.get("stocks", []):
                # 找匹配的标的
                for s in all_stocks:
                    if s["name"] == ns["name"]:
                        node_stocks.append({
                            "name": s["name"],
                            "code": s.get("code", ns.get("code", "")),
                            "pct": s.get("pct", 0),
                            "reason": ns.get("catalyst", s.get("reason", "")),
                        })
                        break
            if node_stocks:
                # 解析节点名称为 上游/中游/下游
                node_name = node.get("level", "")
                if "上游" in node_name:
                    level = "上游"
                elif "中游" in node_name:
                    level = "中游"
                elif "下游" in node_name:
                    level = "下游"
                else:
                    level = node_name

                groups.append({
                    "level": level,
                    "role": node.get("role", ""),
                    "stocks": node_stocks,
                })

        if len(groups) >= 2:
            return groups

    # 自动推导：按推荐理由分组（理由常描述产业位置）
    reason_groups = {}
    for s in all_stocks:
        reason = s.get("reason", "").strip()
        if reason in ("核心标的", "弹性标的", "相关标的", "龙头首选", "弹性机会", "", "前瞻弹性标的", "核心前瞻标的"):
            key = "核心标的"
        else:
            key = reason

        if key not in reason_groups:
            reason_groups[key] = {"stocks": [], "reason": reason}
        reason_groups[key]["stocks"].append({
            "name": s["name"], "code": s.get("code", ""),
            "pct": s.get("pct", 0), "reason": s.get("reason", ""),
        })

    # 简单映射：第一组→上游，最后一组→下游，其余→中游
    keys = list(reason_groups.keys())
    if len(keys) == 1:
        # 单组：全归中游
        level = "中游" if len(all_stocks) > 1 else ""
        return [{"level": level, "role": keys[0][:20], "stocks": reason_groups[keys[0]]["stocks"]}]

    groups = []
    for i, k in enumerate(keys):
        if i == 0:
            level = "上游"
        elif i == len(keys) - 1:
            level = "下游"
        else:
            level = "中游"
        role = k if k != "核心标的" else ""
        groups.append({
            "level": level,
            "role": role[:24],
            "stocks": reason_groups[k]["stocks"],
        })

    return groups


def build_market_summary(topics: list, stocks: list, live_quotes: dict) -> dict:
    """构建市场摘要"""
    if not topics:
        return {}

    sorted_topics = sorted(topics, key=lambda t: t["heat"], reverse=True)
    top_directions = [(t["title"], t["heat"]) for t in sorted_topics[:3]]

    up_count = sum(1 for s in stocks if s.get("pct", 0) > 0)
    down_count = sum(1 for s in stocks if s.get("pct", 0) < 0)

    rising_tags = []
    for t in sorted_topics:
        for g in t.get("chain_groups", []):
            if any(s.get("pct", 0) > 5 for s in g.get("stocks", [])):
                tag = t['title']
                if tag not in rising_tags:
                    rising_tags.append(tag)
                break
        if len(rising_tags) >= 3:
            break

    heat_avg = sum(t["heat"] for t in topics) / len(topics)
    if heat_avg >= 80:
        mood = "市场情绪高涨，机构密集覆盖多个热点方向"
    elif heat_avg >= 60:
        mood = "机构积极布局，结构性机会突出"
    elif heat_avg >= 45:
        mood = "市场轮动加速，关注主线清晰的方向"
    else:
        mood = "市场情绪偏谨慎，精选确定性方向"

    top_keywords = [d[0] for d in top_directions[:2]]
    one_liner = f"{'、'.join(top_keywords)}引领今日热点，{mood}"

    return {
        "top_directions": top_directions,
        "rising_tags": rising_tags,
        "one_liner": one_liner,
        "up_count": up_count,
        "down_count": down_count,
        "total_topics": len(topics),
        "total_opp": 0,
        "total_stocks": len(stocks),
    }


def build_alpha_list(topics: list) -> tuple:
    """构建 Top5 Alpha + 全量精简 Alpha (Top{MAX_ALPHA_DISPLAY})"""
    all_stocks = []
    seen = set()

    for topic in sorted(topics, key=lambda t: t["heat"], reverse=True):
        for g in topic.get("chain_groups", []):
            for s in g.get("stocks", []):
                name = s["name"]
                if name in seen:
                    continue
                seen.add(name)

                topic_heat = topic["heat"] / 100 * 60
                # 产业位置加分: 上游+30, 中游+20, 下游+10
                level = g.get("level", "")
                if level == "上游":
                    pos_bonus = 30
                elif level == "中游":
                    pos_bonus = 20
                elif level == "下游":
                    pos_bonus = 10
                else:
                    pos_bonus = 15
                alpha = min(int(topic_heat + pos_bonus), 99)

                all_stocks.append({
                    "name": name,
                    "alpha": alpha,
                    "reason": s.get("reason", ""),
                    "pct": s.get("pct", 0),
                })

    all_stocks.sort(key=lambda x: x["alpha"], reverse=True)

    top5 = all_stocks[:5]
    rest = all_stocks[5:5 + MAX_ALPHA_DISPLAY]

    return top5, rest


def build_opp_previews(am_opp: list, secids: dict) -> list:
    """构建机会前瞻"""
    previews = []
    for t in am_opp:
        scores = score_topic(t, 0)

        ai_summary, bluebook_quote = _split_summary_v2(t.get("summary_raw", ""))
        if not ai_summary:
            ai_summary = t.get("summary_clean", "")[:150]

        stocks = []
        for i, sname in enumerate(t.get("stocks", [])[:6]):
            sid = secids.get(sname, "")
            stocks.append({
                "name": sname,
                "code": sid,
                "pct": 0,
                "reason": "核心前瞻标的" if i == 0 else "前瞻弹性标的",
            })

        previews.append({
            "title": t["topic"],
            "stage": "孵化",
            "heat": scores["heat_total"],
            "heat_breakdown": {
                "机构关注度": scores["org_attention"],
                "市场确认度": scores["market_confirm"],
                "催化质量": scores["catalyst_quality"],
            },
            "ai_summary": ai_summary,
            "bluebook_quote": bluebook_quote,
            "stocks": stocks,
        })

    return previews


def format_raw_topics(raw_topics: list, secids: dict) -> list:
    """将 raw topic 列表格式化为 pipeline format，并评分排序"""
    formatted = []
    for i, t in enumerate(raw_topics):
        try:
            ft = format_topic_for_pipeline(t, i + 1, secids)
            formatted.append(ft)
        except Exception as e:
            print(f"  ⚠️ 格式化主题失败 [{t.get('topic', '?')}]: {e}")
    formatted.sort(key=lambda x: x["heat"], reverse=True)
    return formatted


# ============================================================
# 主生成函数
# ============================================================

def generate_edition(edition: str, date_str: str, date_display: str,
                     raw_topics: list, raw_opp: list,
                     live_quotes: dict = None, output_path: str = None,
                     mid_reasons_map: dict = None):
    """
    生成单版报告

    Args:
        mid_reasons_map: {topic_title: [{"name":"x","reason":"y"},...]} 午间版专属
    """
    live_quotes = live_quotes or {}
    mid_reasons_map = mid_reasons_map or {}

    # 1. 收集标的 & secid map
    all_stock_names = []
    for t in raw_topics + raw_opp:
        all_stock_names.extend(t.get("stocks", []))
    secids = build_secid_map(all_stock_names)

    # 2. 格式化 & 评分
    formatted = format_raw_topics(raw_topics, secids)

    # 3. 转换为 v3 format
    v3_topics = []
    for i, ft in enumerate(formatted):
        topic_reasons = mid_reasons_map.get(ft["title"], None)
        v3_topics.append(topic_to_v3(ft, i + 1, secids, live_quotes, topic_reasons))

    # 4. 市场摘要
    all_v3_stocks = []
    for t in v3_topics:
        for g in t.get("chain_groups", []):
            all_v3_stocks.extend(g.get("stocks", []))
    market_summary = build_market_summary(v3_topics, all_v3_stocks, live_quotes)
    market_summary["total_opp"] = len(raw_opp)

    # 5. Alpha 列表 (精简)
    top5_alpha, all_alpha = build_alpha_list(v3_topics)

    # 6. 机会前瞻
    opp_previews = build_opp_previews(raw_opp, secids)

    # 7. 报告数据
    edition_labels = {"am": "晨会版", "md": "午间版", "global": "全球版"}
    report_data = {
        "meta": {
            "edition": edition,
            "date": date_str,
            "date_display": date_display,
            "topic_count": len(v3_topics),
            "opp_count": len(opp_previews),
            "stock_count": len(all_stock_names),
            "title": f"蓝宝书Max · {date_display} {edition_labels.get(edition, '')}",
        },
        "market_summary": market_summary,
        "topics": v3_topics,
        "opportunity_previews": opp_previews,
        "top5_alpha": top5_alpha,
        "all_alpha": all_alpha,
        "secid_map": secids,
    }

    # 8. 生成 HTML
    html = generate_report(report_data)

    # 9. 写入文件
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  ✅ {edition_labels.get(edition, edition)}: {output_path} "
              f"({len(html)/1024:.1f} KB, {len(v3_topics)} 主题, {len(secids)} 标的, "
              f"Alpha Top5+{len(all_alpha)})")
    else:
        print(f"  ✅ {edition_labels.get(edition, edition)}: "
              f"({len(html)/1024:.1f} KB, {len(v3_topics)} 主题)")

    return report_data, html


def generate_all():
    """生成所有版本报告"""
    print("📖 解析 Alpha派 数据...")
    reports = parse_reports()
    print(f"   晨会版: {len(reports['am'])} 条")
    print(f"   全球版: {len(reports['global'])} 条")

    # 午间版真实数据
    midday_topics = parse_midday_data()
    if midday_topics:
        print(f"   午间版: {len(midday_topics)} 条 (真实Alpha派午间版)")
    else:
        print("   午间版: 复用晨会版数据 (缺少真实午间版数据)")

    today = datetime.now(CST).strftime("%Y-%m-%d")
    date_display = "2026年6月23日"
    reports_dir = OUTPUT_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # ===== 晨会版 =====
    am_all = reports["am"]
    am_hot = [t for t in am_all if t["section"] == "市场热点"]
    am_opp = [t for t in am_all if t["section"] == "机会前瞻"]

    print(f"\n🌅 生成晨会版...")
    generate_edition(
        edition="am", date_str=today, date_display=date_display,
        raw_topics=am_hot, raw_opp=am_opp,
        output_path=str(reports_dir / "am-20260623.html"),
    )

    # ===== 午间版 (真实数据 + 实时行情) =====
    print(f"\n☀️ 生成午间版（真实午间数据 + 实时行情）...")

    if midday_topics:
        # 使用真实午间版数据
        md_hot = [t for t in midday_topics if t["section"] == "市场热点"]
        md_opp = [t for t in midday_topics if t["section"] == "机会前瞻"]

        # 构建推荐理由映射
        mid_reasons_map = {}
        for t in midday_topics:
            mid_reasons_map[t["topic"]] = t.get("stocks_with_reasons", [])
    else:
        # 回退到晨会版数据
        md_hot = am_hot
        md_opp = am_opp
        mid_reasons_map = {}

    # 拉取实时行情
    all_md_stocks = [s for t in md_hot + md_opp for s in t.get("stocks", [])]
    secids_md = build_secid_map(all_md_stocks)

    try:
        live_quotes = fetch_realtime_quotes(secids_md)
    except Exception as e:
        print(f"  ⚠️ 实时行情拉取失败: {e}，使用默认值")
        live_quotes = {}

    generate_edition(
        edition="md", date_str=today, date_display=date_display,
        raw_topics=md_hot, raw_opp=am_opp,  # 午间用自己数据
        live_quotes=live_quotes,
        mid_reasons_map=mid_reasons_map,
        output_path=str(reports_dir / "md-20260623.html"),
    )

    # ===== 全球版 =====
    global_all = reports["global"]
    global_sections = ("市场热点", "隔夜美股复盘", "全球重点事件梳理", "美股复盘", "全球事件")
    global_hot = [t for t in global_all if t["section"] in global_sections]
    global_opp = [t for t in global_all if t["section"] == "机会前瞻"]

    print(f"\n🌍 生成全球版...")
    generate_edition(
        edition="global", date_str=today, date_display=date_display,
        raw_topics=global_hot, raw_opp=global_opp,
        output_path=str(reports_dir / "global-20260623.html"),
    )

    print(f"\n🎉 全部报告生成完成！")


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="蓝宝书Max v3 报告生成")
    parser.add_argument("--edition", choices=["am", "md", "global", "all"],
                        default="all", help="版本 (默认: all)")
    parser.add_argument("--no-live", action="store_true", help="午间版不拉取实时行情")
    args = parser.parse_args()

    if args.edition == "all":
        generate_all()
    else:
        reports = parse_reports()
        today = datetime.now(CST).strftime("%Y-%m-%d")
        date_display = "2026年6月23日"
        reports_dir = OUTPUT_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        if args.edition in ("am", "md"):
            am_all = reports["am"]
            am_hot = [t for t in am_all if t["section"] == "市场热点"]
            am_opp = [t for t in am_all if t["section"] == "机会前瞻"]

            if args.edition == "md":
                # 午间版用真实数据
                midday_topics = parse_midday_data()
                if midday_topics:
                    md_hot = [t for t in midday_topics if t["section"] == "市场热点"]
                    md_opp = [t for t in midday_topics if t["section"] == "机会前瞻"]
                    mid_reasons_map = {}
                    for t in midday_topics:
                        mid_reasons_map[t["topic"]] = t.get("stocks_with_reasons", [])
                else:
                    md_hot = am_hot
                    md_opp = am_opp
                    mid_reasons_map = {}

                live_quotes = None
                if not args.no_live:
                    secids_md = build_secid_map(
                        [s for t in md_hot + md_opp for s in t.get("stocks", [])]
                    )
                    live_quotes = fetch_realtime_quotes(secids_md)

                generate_edition(
                    edition="md", date_str=today, date_display=date_display,
                    raw_topics=md_hot, raw_opp=am_opp,
                    live_quotes=live_quotes,
                    mid_reasons_map=mid_reasons_map,
                    output_path=str(reports_dir / "md-20260623.html"),
                )
            else:
                generate_edition(
                    edition="am", date_str=today, date_display=date_display,
                    raw_topics=am_hot, raw_opp=am_opp,
                    output_path=str(reports_dir / "am-20260623.html"),
                )
        else:
            global_all = reports["global"]
            generate_edition(
                edition="global", date_str=today, date_display=date_display,
                raw_topics=[t for t in global_all if t["section"] in (
                    "市场热点", "隔夜美股复盘", "全球重点事件梳理", "美股复盘", "全球事件")],
                raw_opp=[t for t in global_all if t["section"] == "机会前瞻"],
                output_path=str(reports_dir / "global-20260623.html"),
            )
