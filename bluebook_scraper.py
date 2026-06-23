#!/usr/bin/env python3
"""
蓝宝书Max 全链路自动化抓取脚本
================================
使用 Playwright 直连本地 Chrome（复用现有登录态），
抓取 Alpha派 蓝宝书热点内容，搭配东财 API 获取股票行情。

用法:
  # 从已登录的 Chrome 抓取晨会版
  python3 bluebook_scraper.py --fetch --edition am

  # 抓取午间版
  python3 bluebook_scraper.py --fetch --edition md

  # 抓取晚间版
  python3 bluebook_scraper.py --fetch --edition pm

  # 手动登录模式（打开浏览器让用户手动登录）
  python3 bluebook_scraper.py --login

  # 指定自定义 Chrome profile 目录
  python3 bluebook_scraper.py --fetch --profile "Profile 1"
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, quote
from typing import Optional

import requests
from playwright.sync_api import sync_playwright, BrowserContext, Page

# ============================================================
# 配置
# ============================================================

# Alpha派 基础 URL
ALPHA_BASE = "https://www.alphapai.com"

# 蓝宝书路由
ROUTES = {
    "hot_topic_list": "/reading/home/hot-topic",
    "am": "/reading/home/hot-topic?edition=am",
    "md": "/reading/home/hot-topic?edition=md",
    "pm": "/reading/home/hot-topic?edition=pm",
    "report_detail": "/home/market-report/detail",
}

# 东财 API
EASTMONEY_SEARCH_URL = "https://searchadapter.eastmoney.com/api/suggest/get"
EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"

# 需要检测本地存储中的登录 token key
AUTH_TOKEN_KEYS = ["USER_AUTH_TOKEN", "token", "auth_token", "access_token"]

# Chrome 用户数据目录（macOS）
CHROME_USER_DATA = os.path.expanduser("~/Library/Application Support/Google/Chrome")

# 输出目录
OUTPUT_DIR = Path.cwd()


def find_chrome_profile() -> Optional[str]:
    """自动找到 Chrome 用户使用的 profile 目录"""
    base = Path(CHROME_USER_DATA)
    candidates = []

    # 检查 Default
    default = base / "Default"
    if default.exists() and (default / "Cookies").exists():
        candidates.append(("Default", default))

    # 检查 Profile 1, Profile 2 等
    for d in base.iterdir():
        if d.is_dir() and d.name.startswith("Profile"):
            cookies = d / "Cookies"
            if cookies.exists():
                mtime = cookies.stat().st_mtime
                candidates.append((d.name, d, mtime))

    if not candidates:
        return None

    # 优先返回最近修改过 Cookies 的 profile（说明正在使用）
    candidates_with_mtime = [
        c for c in candidates if len(c) == 3 and isinstance(c[2], float)
    ]
    if candidates_with_mtime:
        candidates_with_mtime.sort(key=lambda x: x[2], reverse=True)
        return candidates_with_mtime[0][0]

    return candidates[0][0]


def check_chrome_running() -> bool:
    """检测 Chrome 是否正在运行"""
    import subprocess
    try:
        result = subprocess.run(
            ["pgrep", "-l", "Google Chrome"],
            capture_output=True, text=True
        )
        return len(result.stdout.strip()) > 0
    except:
        return False


def start_playwright_context(profile_name: Optional[str] = None, headless: bool = False) -> tuple:
    """
    启动 Playwright 并连接到本地 Chrome session。
    
    使用 Playwright 内置 Chromium 直接读取 Chrome 用户数据目录，
    复用所有 cookies 和 localStorage（无需重新登录）。
    
    注意：Chrome 必须关闭才能读取 profile（Chrome 运行时会锁定 profile 文件）。
    
    Args:
        profile_name: Chrome profile 名称，如 "Default" 或 "Profile 1"
        headless: 是否无头模式
    
    Returns:
        (playwright, context, page)
    """
    if profile_name is None:
        profile_name = find_chrome_profile()
        if profile_name is None:
            print("❌ 找不到 Chrome profile，请先打开 Chrome 并登录 Alpha派")
            sys.exit(1)

    user_data_dir = os.path.join(CHROME_USER_DATA, profile_name)
    print(f"📁 使用 Chrome profile: {user_data_dir}")

    # 检查 Chrome 是否运行中
    if check_chrome_running() and not headless:
        print("\n⚠️  检测到 Chrome 正在运行！")
        print("   Playwright 需要读取 Chrome profile，但 Chrome 运行时会锁定 profile 文件。")
        print("   请先关闭所有 Chrome 窗口，然后重试。")
        print("\n   关闭方法：")
        print("     1. Cmd+Q 完全退出 Chrome（不是关闭窗口）")
        print("     2. 或在终端执行: pkill -a 'Google Chrome'\n")
        sys.exit(1)

    pw = sync_playwright().start()

    try:
        # 使用 Playwright 内置 Chromium，直接读取 Chrome 的用户数据目录
        # 这样所有 cookies、localStorage 都会被复用
        context = pw.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=TranslateUI",
                "--no-first-run",
            ],
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
    except Exception as e:
        error_msg = str(e)
        if "Target page, context or browser has been closed" in error_msg or "profile" in error_msg.lower():
            print("\n❌ 无法打开 Chrome profile（可能 Chrome 仍在运行）")
            print("   请完全退出 Chrome 后重试（Cmd+Q 或 pkill -a 'Google Chrome'）")
            pw.stop()
            sys.exit(1)
        raise

    context.set_default_timeout(30000)
    page = context.new_page()
    return pw, context, page


# ============================================================
# 登录态检测 & 登录流程
# ============================================================

def check_login_status(page: Page) -> bool:
    """检查是否已登录 Alpha派"""
    try:
        # 访问首页触发认证检测
        page.goto(f"{ALPHA_BASE}/reading/home/hot-topic", wait_until="networkidle", timeout=20000)
        time.sleep(2)

        current_url = page.url
        if "/login" in current_url:
            print("  ⚠️ 当前未登录或登录已过期")
            return False

        # 检测页面是否存在蓝宝书内容（说明已登录）
        try:
            page.wait_for_selector(".hot-topic-item, .topic-card, .report-item", timeout=5000)
            print("  ✅ 已登录，检测到蓝宝书内容")
            return True
        except:
            # 可能在其他页面，检查 URL
            if "hot-topic" in current_url:
                print("  ✅ 在蓝宝书页面，假定已登录")
                return True

        print("  ⚠️ 无法确认登录状态")
        return False

    except Exception as e:
        print(f"  ⚠️ 登录检测出错: {e}")
        return False


def cmd_login(profile_name: Optional[str] = None):
    """
    打开可视化浏览器，让用户手动登录 Alpha派。
    登录成功后脚本自动检测 token 并保存。
    """
    print("🔐 启动浏览器，请在页面中手动登录 Alpha派...")
    print("   登录成功后脚本会自动检测并保存登录态，然后你可以关闭浏览器。\n")

    pw, context, page = start_playwright_context(profile_name, headless=False)

    try:
        page.goto(f"{ALPHA_BASE}/reading/home/hot-topic", wait_until="networkidle", timeout=30000)

        print("⏳ 等待登录... (检测到蓝宝书内容后自动完成)")

        # 轮询等待登录成功
        max_wait = 300  # 最多等 5 分钟
        for i in range(max_wait):
            time.sleep(1)
            current_url = page.url
            if "/login" not in current_url and "hot-topic" in current_url:
                print(f"\n✅ 登录成功！登录态已保存到 Chrome profile。")
                break
            if i % 10 == 0 and i > 0:
                print(f"  ... 已等待 {i} 秒，请继续操作")
        else:
            print(f"\n⚠️ 等待超时，如果你已登录成功，登录态会自动保存在 Chrome 中。")

    except Exception as e:
        print(f"❌ 登录流程出错: {e}")
    finally:
        context.close()
        pw.stop()


# ============================================================
# 抓取策略
# ============================================================

def strategy_xhr_intercept(page: Page, target_path: str) -> list[dict]:
    """
    策略3 (最可靠): XHR 拦截
    注入 JS 覆盖 fetch/XMLHttpRequest，重新加载页面，拦截所有 API 响应。
    直接拿到 Alpha派 后端返回的 JSON 数据。
    """
    intercepted_responses = []

    def on_response(response):
        url = response.url
        # 拦截 Alpha派 的 API 响应
        if "alphapai.com" in url and response.headers.get("content-type", "").startswith("application/json"):
            try:
                body = response.json()
                if body:
                    intercepted_responses.append({
                        "url": url,
                        "body": body,
                    })
            except:
                pass

    page.on("response", on_response)
    page.goto(f"{ALPHA_BASE}{target_path}", wait_until="networkidle", timeout=30000)
    time.sleep(3)  # 等待异步数据加载

    return intercepted_responses


def strategy_js_fulltext(page: Page) -> str:
    """
    策略2: JS 全文提取
    不依赖具体 CSS 类名，拿到页面所有可见文本。
    """
    text = page.evaluate("""() => {
        const app = document.querySelector('#app');
        if (app) return app.innerText;
        return document.body.innerText;
    }""")
    return text


def strategy_css_selectors(page: Page) -> list[dict]:
    """
    策略1: CSS 选择器匹配
    尝试多种可能的选择器抓取热点主题。
    """
    selectors = [
        ".hot-topic-item",
        ".topic-card",
        ".report-item",
        ".hot-topic-list > div",
        ".topic-list .topic-item",
        "[class*='topic']",
        "[class*='report']",
    ]

    results = []
    for selector in selectors:
        try:
            elements = page.query_selector_all(selector)
            if elements:
                for el in elements:
                    text = el.inner_text().strip()
                    if text and len(text) > 10:  # 过滤太短的内容
                        href = el.get_attribute("href") or ""
                        results.append({
                            "selector": selector,
                            "text": text,
                            "href": href,
                        })
                if results:
                    break
        except:
            continue

    return results


def extract_stock_names(text: str) -> list[str]:
    """
    从文本中提取 A 股股票名称。
    匹配规则：2-4个中文字符，常见股票命名模式。
    """
    # 中文股票名称通常是 2-4 个字
    # 排除常见非股票词汇
    stop_words = {
        "公司", "集团", "股份", "有限", "技术", "科技", "数据", "信息",
        "市场", "行业", "板块", "指数", "基金", "投资", "分析", "策略",
        "报告", "研究", "建议", "推荐", "关注", "风险", "收益", "预期",
        "政策", "经济", "宏观", "微观", "全球", "国内", "海外", "整体",
        "今日", "昨日", "本周", "本月", "年度", "季度", "上半年", "下半年",
        "增长", "下降", "上涨", "下跌", "买入", "卖出", "持有", "增持",
        "发布", "公告", "业绩", "财报", "营收", "利润", "净利润",
        "我们", "他们", "这个", "那个", "可以", "可能", "已经",
    }

    # 匹配中文股票名称（2-4个字，在上下文中独立出现）
    # 更精确的匹配：跟在"关注"、"推荐"、"买入"等词后面，或者单独成行
    patterns = [
        r'(?:关注|推荐|看好|买入|增持|重点)\s*[:：]?\s*([\u4e00-\u9fff]{2,4})',
        r'[（(]([\u4e00-\u9fff]{2,4})[)）]',
        r'(?:个股|标的)[:：]?\s*([\u4e00-\u9fff]{2,4})',
    ]

    stocks = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            if m not in stop_words and len(m) >= 2:
                stocks.add(m)

    # 如果以上都没匹配到，尝试更宽松的匹配
    # 找独立出现的 2-4 字中文词，前后是标点/空格/换行
    if len(stocks) < 3:
        loose = re.findall(r'(?:^|\n|。|，|、|\s)([\u4e00-\u9fff]{2,4})(?:\n|。|，|、|\s|$)', text)
        for m in loose:
            if m not in stop_words and len(m) >= 2:
                stocks.add(m)

    return list(stocks)


def lookup_stock_codes(stock_names: list[str]) -> dict[str, dict]:
    """
    通过东财搜索 API 将股票名称转换为 secid。

    Returns:
        {name: {"secid": "1.603986", "code": "603986", "market": "SH/SZ"}}
    """
    stock_map = {}
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.eastmoney.com/",
    })

    for name in stock_names:
        try:
            params = {
                "input": name,
                "type": "14",
                "token": "D43BF722C8E33BDC906FB84A85E326E8",
                "count": "5",
            }
            resp = session.get(EASTMONEY_SEARCH_URL, params=params, timeout=10)
            data = resp.json()

            if data.get("QuotationCodeTable") and data["QuotationCodeTable"].get("Data"):
                results = data["QuotationCodeTable"]["Data"]
                for r in results:
                    # 筛选 A 股
                    code = r.get("Code", "")
                    market = r.get("MktNum", "")
                    stock_name = r.get("Name", "")
                    if code and market:
                        secid = f"{market}.{code}"
                        stock_map[name] = {
                            "secid": secid,
                            "code": code,
                            "market": "SH" if str(market) == "1" else "SZ",
                            "matched_name": stock_name,
                        }
                        print(f"  🔍 {name} → {stock_name}({secid})")
                        break
        except Exception as e:
            print(f"  ⚠️ 查询 {name} 失败: {e}")

    return stock_map


def fetch_stock_prices(secids: list[str]) -> dict[str, dict]:
    """
    批量获取东财行情数据。

    Returns:
        {secid: {"price": 100.5, "change_pct": 2.3, "name": "兆易创新"}}
    """
    if not secids:
        return {}

    prices = {}
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    })

    # 分批，每批 50 个
    batch_size = 50
    for i in range(0, len(secids), batch_size):
        batch = secids[i:i + batch_size]
        try:
            params = {
                "fltt": "2",
                "fields": "f2,f3,f4,f12,f14",
                "secids": ",".join(batch),
            }
            resp = session.get(EASTMONEY_QUOTE_URL, params=params, timeout=10)
            data = resp.json()

            if data.get("data") and data["data"].get("diff"):
                for item in data["data"]["diff"]:
                    code = item.get("f12", "")
                    name = item.get("f14", "")
                    price = item.get("f2")
                    change_pct = item.get("f3")
                    change_val = item.get("f4")

                    secid_key = f"1.{code}" if not code.startswith("0") else f"0.{code}"
                    # 尝试匹配
                    for sid in batch:
                        if sid.endswith(f".{code}"):
                            prices[sid] = {
                                "name": name,
                                "price": price,
                                "change_pct": change_pct,
                                "change_val": change_val,
                                "code": code,
                            }
                            break

                print(f"  📊 批量获取 {len(batch)} 只股票行情完成")
        except Exception as e:
            print(f"  ⚠️ 批量获取行情失败: {e}")

    return prices


# ============================================================
# 主抓取命令
# ============================================================

def cmd_fetch(edition: str = "am", profile_name: Optional[str] = None, headless: bool = True):
    """
    无人值守抓取蓝宝书内容。
    
    流程:
    1. 启动 Playwright 连接本地 Chrome（复用登录态）
    2. 导航到蓝宝书热点页
    3. 用三层策略抓取内容
    4. 提取股票名称 → 查东财 secid → 拉行情
    5. 输出 JSON
    """
    print(f"\n{'='*60}")
    print(f"  蓝宝书Max 自动抓取 - {edition.upper()} 版本")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 启动浏览器
    print("🌐 启动浏览器...")
    pw, context, page = start_playwright_context(profile_name, headless=headless)

    try:
        # 导航到蓝宝书页面
        target_path = ROUTES.get(edition, ROUTES["hot_topic_list"])
        print(f"📖 导航到: {ALPHA_BASE}{target_path}")

        # 策略3：XHR 拦截（首选）
        print("\n📡 策略3: XHR 拦截...")
        api_responses = strategy_xhr_intercept(page, target_path)

        # 从 API 响应中提取数据
        raw_topics = []
        for resp in api_responses:
            body = resp.get("body", {})
            url = resp.get("url", "")

            # 尝试从多种 API 响应格式中提取热点数据
            if isinstance(body, dict):
                # 检查常见的数据字段
                for key in ["data", "result", "list", "items", "records", "topics", "hotTopics", "reports"]:
                    items = body.get(key)
                    if isinstance(items, list) and items:
                        raw_topics.extend(items)
                        print(f"  ✅ 从 {url} 的 '{key}' 字段提取 {len(items)} 条数据")
                        break

                # 如果 data 包了一层
                if not raw_topics and "data" in body:
                    data = body["data"]
                    if isinstance(data, dict):
                        for key in ["list", "items", "records", "topics", "hotTopics", "reports"]:
                            items = data.get(key)
                            if isinstance(items, list) and items:
                                raw_topics.extend(items)
                                print(f"  ✅ 从 {url} 的 'data.{key}' 字段提取 {len(items)} 条数据")
                                break
                    elif isinstance(data, list):
                        raw_topics.extend(data)
                        print(f"  ✅ 从 {url} 的 'data' 字段提取 {len(data)} 条数据")

        if raw_topics:
            print(f"  🎯 XHR 拦截成功: 获取 {len(raw_topics)} 条数据")
        else:
            print("  ⚠️ XHR 拦截未获取到结构化数据，尝试其他策略")

        # 策略2：JS 全文提取
        print("\n📝 策略2: JS 全文提取...")
        full_text = strategy_js_fulltext(page)
        if full_text:
            print(f"  ✅ 提取到 {len(full_text)} 字符")

        # 策略1：CSS 选择器
        print("\n🎯 策略1: CSS 选择器匹配...")
        css_results = strategy_css_selectors(page)
        if css_results:
            print(f"  ✅ CSS 选择器匹配到 {len(css_results)} 个元素")
        else:
            print("  ⚠️ CSS 选择器未匹配到内容")

        # 提取股票名称
        all_text = full_text
        if not all_text and css_results:
            all_text = "\n".join([r["text"] for r in css_results])

        stock_names = extract_stock_names(all_text) if all_text else []
        print(f"\n📈 从内容中提取到 {len(stock_names)} 只股票: {stock_names}")

        # 查 secid
        print("\n🔍 查询股票代码...")
        stock_map = lookup_stock_codes(stock_names)

        # 拉行情
        if stock_map:
            secids = [info["secid"] for info in stock_map.values()]
            print(f"\n📊 获取行情数据 ({len(secids)} 只)...")
            prices = fetch_stock_prices(secids)

            # 合并数据
            stocks_data = []
            for name, info in stock_map.items():
                secid = info["secid"]
                price_info = prices.get(secid, {})
                stocks_data.append({
                    "name": name,
                    "matched_name": info.get("matched_name", name),
                    "code": info["code"],
                    "secid": secid,
                    "market": info["market"],
                    "price": price_info.get("price"),
                    "change_pct": price_info.get("change_pct"),
                    "change_val": price_info.get("change_val"),
                })
        else:
            stocks_data = []

        # 构建输出
        output = {
            "meta": {
                "edition": edition,
                "scrape_time": datetime.now().isoformat(),
                "source": "bluebook_scraper.py + Playwright",
            },
            "raw_topics": raw_topics if raw_topics else None,
            "raw_text": full_text[:5000] if full_text and not raw_topics else None,
            "css_results": [r["text"] for r in css_results] if css_results and not raw_topics else None,
            "stocks": stocks_data,
            "stock_count": len(stocks_data),
        }

        # 保存
        date_str = datetime.now().strftime("%Y%m%d")
        output_file = OUTPUT_DIR / f"data-{edition}-{date_str}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"  ✅ 抓取完成")
        print(f"  📄 输出文件: {output_file}")
        print(f"  📊 股票数量: {len(stocks_data)}")
        if stocks_data:
            for s in stocks_data:
                price_str = f"¥{s['price']}" if s.get("price") else "N/A"
                change_str = f"{s.get('change_pct', 'N/A')}%" if s.get("change_pct") else "N/A"
                print(f"     {s['name']}({s['code']}) {price_str} {change_str}")
        print(f"{'='*60}\n")

        return str(output_file)

    except Exception as e:
        print(f"\n❌ 抓取出错: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        context.close()
        pw.stop()


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="蓝宝书Max 全链路自动化抓取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --login              # 手动登录（打开浏览器）
  %(prog)s --fetch --edition am  # 抓取晨会版
  %(prog)s --fetch --edition pm --headless  # 无头模式抓取晚间版
  %(prog)s --fetch --profile "Profile 1"    # 指定 Chrome profile
        """,
    )
    parser.add_argument("--login", action="store_true", help="手动登录模式")
    parser.add_argument("--fetch", action="store_true", help="自动抓取模式")
    parser.add_argument("--edition", choices=["am", "md", "pm"], default="am", help="蓝宝书版本 (default: am)")
    parser.add_argument("--profile", help="Chrome profile 名称，如 'Default' 或 'Profile 1'")
    parser.add_argument("--headless", action="store_true", default=True, help="无头模式 (默认)")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口（调试用）")
    parser.add_argument("--check-login", action="store_true", help="仅检查登录状态")

    args = parser.parse_args()

    # 确定 profile
    profile_name = args.profile
    if profile_name is None:
        profile_name = find_chrome_profile()
        if profile_name:
            print(f"🔍 自动检测到 Chrome profile: {profile_name}")
        else:
            print("❌ 未找到 Chrome profile，请用 --profile 指定")
            sys.exit(1)

    headless = args.headless and not args.no_headless

    if args.login:
        cmd_login(profile_name)
    elif args.check_login:
        pw, context, page = start_playwright_context(profile_name, headless=False)
        try:
            is_logged = check_login_status(page)
            if is_logged:
                print("\n✅ Alpha派 已登录")
            else:
                print("\n❌ Alpha派 未登录，请运行 --login 登录")
        finally:
            context.close()
            pw.stop()
    elif args.fetch:
        result = cmd_fetch(args.edition, profile_name, headless)
        if result:
            print("🎉 抓取成功！")
            sys.exit(0)
        else:
            print("💥 抓取失败！")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
