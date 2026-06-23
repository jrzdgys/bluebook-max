#!/usr/bin/env python3
"""
批量报告生成器 (v3)
==================
GitHub Actions 入口：从已提交的 Alpha 派数据生成所有版报告。
用 generate_v3.py 的数据驱动管道。

用法:
  python3 generate_all_reports.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from generate_v3 import generate_all


def main():
    print("🚀 蓝宝书Max v3 · GitHub Actions 批量报告生成")
    generate_all()


if __name__ == "__main__":
    main()
