#!/usr/bin/env python3
"""
蓝宝书Max 导航清单更新器
=======================
扫描目录中的所有 HTML 报告，生成/更新 manifest.json 导航索引。

用法:
  python3 update_manifest.py
"""

import json
from datetime import datetime
from pathlib import Path


OUTPUT_DIR = Path(__file__).parent
REPORTS_DIR = OUTPUT_DIR / "output" / "reports"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"


def update_manifest():
    """扫描 HTML 报告和 JSON 数据，更新 manifest.json"""
    reports = []

    # 扫描 output/reports/ 和根目录
    search_dirs = [REPORTS_DIR, OUTPUT_DIR]
    seen = set()

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for f in sorted(search_dir.glob("*-*.html"), reverse=True):
            name = f.stem  # e.g., "am-20260623"
            parts = name.split("-")
            if len(parts) < 2:
                continue
            edition = parts[0]
            date_str = parts[1]

            if edition not in ("am", "md", "pm", "noon", "global", "mc", "gv", "ev"):
                continue

            # 去重
            key = f"{edition}-{date_str}"
            if key in seen:
                continue
            seen.add(key)

            edition_labels = {
                "am": "晨会版", "mc": "晨会版",
                "md": "午间版", "noon": "午间版", "pm": "午间版",
                "ev": "晚间版",
                "global": "全球版", "gv": "全球版",
            }
            label = edition_labels.get(edition, edition.upper())

            try:
                date_display = datetime.strptime(date_str, "%Y%m%d").strftime("%Y年%m月%d日")
            except ValueError:
                date_display = date_str

            # Try to get stock_count from JSON data
            stock_count = 0
            data_file = OUTPUT_DIR / f"data-{edition}-{date_str}.json"
            if data_file.exists():
                try:
                    with open(data_file, "r", encoding="utf-8") as df:
                        jdata = json.load(df)
                        stock_count = jdata.get("stock_count", len(jdata.get("stocks", [])))
                except:
                    pass

            # 确定 file 路径
            if REPORTS_DIR in f.parents:
                rel_file = f"reports/{f.name}"
            else:
                rel_file = f.name

            reports.append({
                "file": rel_file,
                "edition": edition,
                "label": f"{label}",
                "date": date_str,
                "date_display": date_display,
                "title": f"蓝宝书Max {label} - {date_display}",
                "stock_count": stock_count,
            })

    manifest = {
        "name": "蓝宝书Max",
        "description": "Alpha派蓝宝书热点自动抓取与分析报告",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated": datetime.now().isoformat(),
        "total_reports": len(reports),
        "reports": reports,
    }

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"✅ manifest 已更新: {MANIFEST_FILE}")
    print(f"   📊 共 {len(reports)} 份报告")

    for r in reports[:10]:
        print(f"   📄 {r['file']} - {r['title']}")


if __name__ == "__main__":
    update_manifest()
