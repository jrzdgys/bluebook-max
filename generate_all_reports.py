#!/usr/bin/env python3
"""
批量报告生成器
==============
扫描所有 data-*.json 文件，为每个生成对应的 HTML 报告。
GitHub Actions 用这个脚本从已提交的数据生成报告。

用法:
  python3 generate_all_reports.py
"""
import json
import sys
from pathlib import Path
from generate_report import generate_report

OUTPUT_DIR = Path(__file__).parent


def main():
    data_files = sorted(OUTPUT_DIR.glob("data-*.json"))
    if not data_files:
        print("⚠️ 没有找到数据文件，跳过报告生成")
        return

    generated = 0
    for df in data_files:
        name = df.stem  # e.g., "data-am-20260623"
        parts = name.replace("data-", "").split("-")
        if len(parts) >= 2:
            edition = parts[0]
            try:
                report_file = generate_report(str(df), edition)
                generated += 1
                print(f"  ✅ {df.name} → {Path(report_file).name}")
            except Exception as e:
                print(f"  ❌ {df.name}: {e}")

    print(f"\n🎉 共生成 {generated} 份报告")


if __name__ == "__main__":
    main()
