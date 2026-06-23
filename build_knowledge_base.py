#!/usr/bin/env python3
"""从Alpha派API原始数据抽取结构化知识库 + 生成真实报告"""

import json, re, os
from pathlib import Path

REPORT_JSON = Path("data/reports_2026-06-23.json")
OUT_DIR = Path("data")

def extract_stocks(summary):
    """从蓝宝书摘要中提取加粗的标的名称"""
    stocks = re.findall(r'\*\*(.+?)\*\*', summary)
    # 过滤掉过长的非标的名词
    return [s for s in stocks if len(s) <= 12 and '/' not in s]

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

        # 去重
        if output[key]:
            continue

        sections = r.get("contentJson", [])
        for s in sections:
            for t in s.get("children", []):
                stocks = extract_stocks(t.get("summary", ""))
                # 清理 HTML 标签
                clean_summary = re.sub(r'<[^>]+>', '', t["summary"])
                clean_summary = re.sub(r'\*\*', '', clean_summary)

                output[key].append({
                    "section": s["title"],
                    "topic": t["topicName"],
                    "heat": t.get("index", 5),
                    "summary_raw": t.get("summary", ""),
                    "summary_clean": clean_summary,
                    "stocks": stocks,
                    "id": t.get("id", 0),
                })

    return output

def build_knowledge_md(reports):
    """生成知识库 Markdown"""
    lines = []
    lines.append("# 蓝宝书Max · 2026-06-23 知识库\n")
    lines.append("> 数据来源：Alpha派蓝宝书（通过CDP协议直接调用API获取）")
    lines.append("> API: https://alphapai-web.rabyte.cn/external/alpha/api/\n")

    labels = {"am": "🌅 晨会版", "global": "🌍 全球版"}

    for key in ["am", "global"]:
        topics = reports[key]
        lines.append(f"## {labels[key]}\n")

        sections = {}
        for t in topics:
            s = t["section"]
            if s not in sections:
                sections[s] = []
            sections[s].append(t)

        for sname, sitems in sections.items():
            lines.append(f"### {sname}\n")
            for t in sitems:
                lines.append(f'**{t["topic"]}** [热度:{t["heat"]}/10]')
                if t["stocks"]:
                    lines.append(f'  📊 标的：{", ".join(t["stocks"][:10])}')
                desc = t["summary_clean"]
                if len(desc) > 240:
                    desc = desc[:240] + "..."
                lines.append(f"  📝 {desc}")
                lines.append("")
        lines.append("")

    lines.append("---")
    lines.append(f"*共 {sum(len(v) for v in reports.values())} 条热点，覆盖 {len(reports['am'])} 条晨会版 + {len(reports['global'])} 条全球版*")

    return "\n".join(lines)

def main():
    print("📖 解析 Alpha派 真实报告数据...")
    reports = parse_reports()
    print(f"   晨会版: {len(reports['am'])} 条")
    print(f"   全球版: {len(reports['global'])} 条")

    # 保存结构化数据
    OUT_DIR.mkdir(exist_ok=True)
    for key in reports:
        path = OUT_DIR / f"real_{key}_20260623.json"
        with open(path, "w") as f:
            json.dump(reports[key], f, ensure_ascii=False, indent=2)
        print(f"   {path}")

    # 生成知识库
    md = build_knowledge_md(reports)
    md_path = Path("BLUEBOOK_KNOWLEDGE_BASE.md")
    with open(md_path, "w") as f:
        f.write(md)
    print(f"\n📚 知识库: {md_path} ({len(md.splitlines())} 行)")

    return reports

if __name__ == "__main__":
    main()
