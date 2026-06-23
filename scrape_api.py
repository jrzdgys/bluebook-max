#!/usr/bin/env python3
"""通过CDP浏览器直接调用Alpha派API，获取蓝宝书报告数据"""
import asyncio, json, subprocess, time
from playwright.async_api import async_playwright

CDP_URL = "http://127.0.0.1:9222"
API_BASE = "https://alphapai-web.rabyte.cn/external/alpha/api"

def start_chrome():
    subprocess.run(["pkill", "-f", "Google Chrome"], capture_output=True)
    time.sleep(1)
    subprocess.Popen([
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--remote-debugging-port=9222", "--user-data-dir=/tmp/chrome_minimal",
        "--no-sandbox", "--disable-gpu-sandbox", "--disable-setuid-sandbox",
        "--disable-gpu", "--disable-software-rasterizer", "--no-first-run",
        "--profile-directory=Profile 1", "--disable-extensions",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        try:
            import urllib.request
            urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2)
            return True
        except: time.sleep(0.5)
    return False

async def api_fetch(page, url, method="GET"):
    """在浏览器上下文中调用API"""
    result = await page.evaluate("""
        async ([url, method]) => {
            try {
                const resp = await fetch(url, {
                    method: method,
                    headers: {
                        'Accept': 'application/json, text/plain, */*',
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include'
                });
                const text = await resp.text();
                return {
                    status: resp.status,
                    ok: resp.ok,
                    text: text.substring(0, 5000),
                    headers: Object.fromEntries(resp.headers.entries())
                };
            } catch(e) {
                return {error: e.message};
            }
        }
    """, [url, method])
    return result

async def main():
    if not start_chrome(): return

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL, timeout=5000)
        context = browser.contexts[0]
        page = await context.new_page()

        # 先导航到首页，激活session
        print("🔍 导航到首页...")
        await page.goto("https://alphapai-web.rabyte.cn/", wait_until="load", timeout=30000)
        await asyncio.sleep(3)
        print(f"✅ 已登录: {page.url}")

        # API端点列表
        apis = [
            ("用户信息", f"{API_BASE}/v2/authorization/user/info"),
            ("最新报告v2", f"{API_BASE}/mix/hot/topic/report/latest/v2"),
            ("热门报告推荐", f"{API_BASE}/reading/report/hot/recommend"),
            ("今日阅读数", f"{API_BASE}/reading/count/today"),
            ("当前批次列表", f"{API_BASE}/mix/hot/topic/current/batch/list?more=true"),
            ("热门话题股票", f"{API_BASE}/mix/hot/topic/stock/list"),
            ("批次更新时间", f"{API_BASE}/mix/hot/topic/current/batch/list/update/time"),
            ("路演推荐", f"{API_BASE}/reading/roadshow/summary/hot/recommend"),
        ]

        results = {}
        for name, url in apis:
            print(f"\n📡 [{name}] {url.split('/')[-1][:50]}...")
            resp = await api_fetch(page, url)
            status = resp.get("status", "ERR")
            ok = resp.get("ok", False)
            text = resp.get("text", "")[:300]
            error = resp.get("error", "")
            print(f"   status={status} ok={ok}")
            if ok:
                try:
                    data = json.loads(resp.get("text", "{}"))
                    print(f"   data keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
                    # 预览前200字符
                    preview = json.dumps(data, ensure_ascii=False)[:200]
                    print(f"   preview: {preview}")
                except:
                    print(f"   raw: {text[:200]}")
            else:
                print(f"   error: {error or text[:200]}")
            results[name] = resp

        # 保存完整结果
        with open("/tmp/alpha_api_results.json", "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 完整API结果: /tmp/alpha_api_results.json")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
