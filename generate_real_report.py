#!/usr/bin/env python3
"""
蓝宝书Max · 从Alpha派真实数据生成报告
数据来源：data/reports_2026-06-23.json（通过CDP协议截获API响应）
"""
import json, sys, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pipeline_v2 import generate_report_html, load_design_system, OUTPUT_DIR
from build_knowledge_base import parse_reports

# 东方财富 secid 映射（标的代码→secid）
SECID_MAP = {}

def build_secid_map():
    """构建标的名称到东方财富secid的映射"""
    code_map = {
        "长川科技": "0.300604", "华峰测控": "1.688200", "精智达": "1.688627",
        "金海通": "1.603061", "强一股份": "1.688552",
        "英伟达": "", "强瑞技术": "0.301128", "金富科技": "0.003018",
        "飞龙股份": "0.002536", "申菱环境": "0.301018", "高澜股份": "0.300499",
        "英维克": "0.002837", "和胜股份": "0.002824",
        "建滔积层板": "", "生益科技": "1.600183", "华正新材": "1.603186",
        "金安国纪": "0.002636", "中国巨石": "1.600176", "中材科技": "0.002080",
        "宏和科技": "1.603256", "国际复材": "0.301526", "德福科技": "0.301511",
        "圣泉集团": "1.605589", "东材科技": "1.601208",
        "兆易创新": "1.603986", "北京君正": "0.300223", "普冉股份": "1.688766",
        "东芯股份": "1.688110", "江波龙": "0.301308", "佰维存储": "1.688525",
        "德明利": "0.001309", "大普微": "", "澜起科技": "1.688008",
        "中信证券": "1.600030", "广发证券": "0.000776", "国泰海通": "1.601211",
        "华泰证券": "1.601688", "招商证券": "1.600999", "东方财富": "0.300059",
        "同花顺": "0.300033", "中金公司": "1.601995",
        "云天化": "1.600096", "兴发集团": "1.600141", "川恒股份": "0.002895",
        "川发龙蟒": "0.002312", "云图控股": "0.002539", "新洋丰": "0.000902",
        "芭田股份": "0.002170",
        "凯盛科技": "1.600552", "旗滨集团": "1.601636", "戈碧迦": "1.835438",
        "帝尔激光": "0.300776", "德龙激光": "1.688170", "东威科技": "1.688700",
        "芯碁微装": "1.688630", "京东方A": "0.000725", "沃格光电": "1.603773",
        "长飞光纤": "1.601869", "亨通光电": "1.600487", "中天科技": "1.600522",
        "烽火通信": "1.600498", "太辰光": "0.300570", "仕佳光子": "1.688313",
        "中国动力": "1.600482", "应流股份": "1.603308", "杰瑞股份": "0.002353",
        "潍柴动力": "0.000338", "联德股份": "1.605060", "天润工业": "0.002283",
        "三环集团": "0.300408",
        "国瓷材料": "0.300285", "爱迪特": "0.301580", "东方锆业": "0.002167",
        "龙佰集团": "0.002601", "西陇科学": "0.002584", "三祥新材": "1.603663",
        "长电科技": "1.600584", "通富微电": "0.002156", "华天科技": "0.002185",
        "盛合晶微": "", "大族激光": "0.002008", "联瑞新材": "1.688300",
        "天承科技": "1.688601",
        "科济药业": "", "传奇生物": "", "药明巨诺": "", "金斯瑞生物科技": "",
        "国机精工": "0.002046", "四方达": "0.300179", "沃尔德": "1.688028",
        "力量钻石": "0.301071", "惠丰钻石": "1.839725", "中兵红箭": "0.000519",
        "恒盛能源": "1.605580", "共达电声": "0.002655",
        "中钨高新": "0.000657", "厦门钨业": "1.600549", "欧科亿": "1.688308",
        "华锐精密": "1.688059", "新锐股份": "1.688257", "鼎泰高科": "0.301377",
        "江钨装备": "",
        "拓普集团": "1.601689", "三花智控": "0.002050", "科达利": "0.002850",
        "斯菱智驱": "0.301550", "峰岹科技": "1.688279", "恒帅股份": "0.300969",
        "福赛科技": "0.301529", "贝斯特": "0.300580", "恒立液压": "1.601100",
        "浙江荣泰": "1.603119",
        "宁德时代": "0.300750",
        "智谱": "", "剑桥科技": "1.603083",
        # 全球版
        "美光": "", "MU": "", "英特尔": "", "INTC": "",
        "Getty": "", "GETY": "", "Coherent": "", "COHR": "",
        "LRCX": "", "AMAT": "", "奈飞": "", "NFLX": "",
        "安森美": "", "ON": "", "维谛技术": "", "VRT": "",
        "Palantir": "", "PLTR": "", "博通": "", "AVGO": "",
        "SpaceX": "", "SPCX": "",
        "Meta": "", "Cred": "", "艾伯维": "", "AbbVie": "",
        "Apogee": "", "高通": "", "Qualcomm": "", "Modular": "",
        "Robinhood": "", "CRH": "", "Arcosa": "",
        "雪佛龙": "", "Chevron": "", "微软": "", "Microsoft": "",
        "Groq": "", "Lucid": "",
    }
    return code_map

def format_topic_for_pipeline(topic, rank):
    """将Alpha派原始主题格式化为pipeline期望的格式"""
    heat = topic["heat"] * 10  # Alpha派 1-10 scale → 0-100 scale

    # 状态判断
    if heat >= 80:
        state = "主升"
    elif heat >= 60:
        state = "强化"
    elif heat >= 40:
        state = "持续"
    else:
        state = "孵化"

    # 构建标的列表（从摘要中提取的加粗标的）
    stocks_data = []
    stocks = topic.get("stocks", [])
    if stocks:
        # 龙头首选：前2个
        leader_items = []
        for s in stocks[:2]:
            leader_items.append({
                "name": s, "code": "", "reason": "核心标的",
                "change_pct": 0,
            })
        if leader_items:
            stocks_data.append({"tier": "龙头首选", "label": "龙头首选", "items": leader_items})

        # 弹性机会：第3-4个
        flex_items = []
        for s in stocks[2:4]:
            flex_items.append({
                "name": s, "code": "", "reason": "弹性标的",
                "change_pct": 0,
            })
        if flex_items:
            stocks_data.append({"tier": "弹性机会", "label": "弹性机会", "items": flex_items})

        # 相关标的：其余
        rest_items = []
        for s in stocks[4:]:
            rest_items.append({
                "name": s, "code": "", "reason": "相关标的",
                "change_pct": 0,
            })
        if rest_items:
            stocks_data.append({"tier": "相关标的", "label": "相关标的", "items": rest_items})

    return {
        "title": topic["topic"],
        "summary": topic["summary_clean"][:120],
        "bluebook_quote": topic["summary_clean"][:200],
        "heat": heat,
        "state": state,
        "org_attention": int(heat * 0.6),
        "market_confirm": int(heat * 0.25),
        "catalyst_quality": int(heat * 0.15),
        "stocks": stocks_data,
        "raw_stocks": stocks,
    }

def make_sentiment_summary(topics, version):
    """生成市场情绪一句话总结"""
    if not topics:
        return "今日无热点主题", "观望"

    top_heats = sorted(topics, key=lambda t: t["heat"], reverse=True)[:5]
    top_names = [t["topic"][:12] for t in top_heats[:3]]
    avg_heat = sum(t["heat"] * 10 for t in topics) / len(topics)

    if avg_heat >= 75:
        signal = "强势做多"
        signal_cls = "signal-bullish"
    elif avg_heat >= 60:
        signal = "积极看多"
        signal_cls = "signal-bullish"
    elif avg_heat >= 45:
        signal = "结构性轮动"
        signal_cls = "signal-neutral"
    else:
        signal = "谨慎观望"
        signal_cls = "signal-neutral"

    if version == "global":
        summary = f"全球市场：{'、'.join(top_names)}领涨，AI算力与存储板块持续走强"
    else:
        summary = f"最强方向：{'、'.join(top_names)}领衔，市场情绪{signal}"

    return summary, signal

def generate_am_report():
    """生成晨会版报告"""
    print("🌅 生成晨会版报告...")
    reports = parse_reports()
    topics = reports["am"]

    # 分离市场热点和机会前瞻
    hot_topics = [t for t in topics if t["section"] == "市场热点"]
    opp_topics = [t for t in topics if t["section"] == "机会前瞻"]

    # 格式化主题
    formatted = [format_topic_for_pipeline(t, i+1) for i, t in enumerate(hot_topics)]
    formatted_opp = [format_topic_for_pipeline(t, 0) for t in opp_topics]

    summary, signal = make_sentiment_summary(hot_topics, "am")

    # 构建Alpha精选（取热度最高的top5）
    sorted_formatted = sorted(formatted, key=lambda x: x["heat"], reverse=True)
    alpha_top5 = []
    for f in sorted_formatted[:5]:
        stocks = f.get("raw_stocks", [])
        first_stock = stocks[0] if stocks else "—"
        alpha_top5.append({
            "name": first_stock,
            "code": "",
            "alpha": f["heat"],
            "reason": f["title"][:30],
            "change_pct": 0,
        })

    # 添加secid（为实时行情用）
    secid_map = build_secid_map()
    used_secids = {}
    for f in formatted:
        for tier in f.get("stocks", []):
            for s in tier.get("items", []):
                name = s["name"]
                if name in secid_map and secid_map[name]:
                    used_secids[name] = secid_map[name]

    stats = {
        "total_topics": len(formatted),
        "total_stocks": sum(len(t.get("stocks", [])) for t in hot_topics),
        "total_opportunities": len(formatted_opp),
        "market_signal": signal,
        "summary": summary,
        "alpha_top5": alpha_top5,
        "opportunities": [
            {
                "title": t["topic"],
                "summary": t["summary_clean"][:100],
                "bluebook_quote": t["summary_clean"][:200],
            }
            for t in opp_topics
        ],
        "secid_map": used_secids,
    }

    # 生成HTML
    css = load_design_system()
    html = generate_report_html(
        title="蓝宝书 · 2026-06-23 晨会版",
        date_str="2026年06月23日",
        version="am",
        topics=formatted,
        statistics=stats,
        design_css=css,
    )

    reports_dir = OUTPUT_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "am-20260623.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ {path} ({len(html)/1024:.1f} KB, {len(formatted)}主题)")

def generate_global_report():
    """生成全球版报告"""
    print("🌍 生成全球版报告...")
    reports = parse_reports()
    topics = reports["global"]

    # 分离美股复盘和全球事件
    us_topics = [t for t in topics if "美股" in t["section"] or "复盘" in t["section"]]
    global_topics = [t for t in topics if "全球" in t["section"] or "事件" in t["section"]]

    all_formatted = [format_topic_for_pipeline(t, i+1) for i, t in enumerate(topics)]
    summary, signal = make_sentiment_summary(topics, "global")

    stats = {
        "total_topics": len(all_formatted),
        "total_stocks": 0,
        "total_opportunities": len(global_topics),
        "market_signal": signal,
        "summary": summary,
        "alpha_top5": [],
        "opportunities": [
            {"title": t["topic"], "summary": t["summary_clean"][:100], "bluebook_quote": t["summary_clean"][:200]}
            for t in global_topics
        ],
        "secid_map": {},
    }

    css = load_design_system()
    html = generate_report_html(
        title="蓝宝书 · 2026-06-23 全球版",
        date_str="2026年06月23日",
        version="global",
        topics=all_formatted,
        statistics=stats,
        design_css=css,
    )

    reports_dir = OUTPUT_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "global-20260623.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ {path} ({len(html)/1024:.1f} KB, {len(all_formatted)}主题)")

if __name__ == "__main__":
    generate_am_report()
    generate_global_report()
    print("\n🎉 两份报告全部生成！")
