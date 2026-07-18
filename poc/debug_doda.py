"""doda の検索ページ構造を調査する。

確認ポイント:
- 求人検索の URL（クエリ送信方法）
- 1 ページの listing 数
- 会社名・求人 URL の取得経路
- ページネーション
"""
from __future__ import annotations
import asyncio
import re
from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


async def main():
    out = Path("output/doda_debug")
    out.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-http2",
                "--disable-features=NetworkService",
            ],
        )
        ctx = await browser.new_context(
            user_agent=UA, locale="ja-JP", timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
            extra_http_headers={"Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8"},
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await ctx.new_page()

        # 1. トップ
        for url in [
            "https://doda.jp/",
            "https://doda.jp/DodaFront/View/JobSearchList/",
            "https://doda.jp/DodaFront/View/JobSearchList.action",
            "https://doda.jp/DodaFront/View/JobSearchList.action?ka=1",  # 全国/全件想定
        ]:
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_timeout(1500)
                status = resp.status if resp else "?"
                title = await page.title()
                final = page.url
                print(f"[{status}] {url}")
                print(f"  -> final={final}")
                print(f"  -> title={title!r}")
                # 会社名 / 求人カード候補
                content = await page.content()
                # よくある class 名
                for selector in ["dl.dailyJobs", ".jobList", ".searchResult", ".joblist", ".company", ".companyName"]:
                    cnt = content.count(f'class="{selector.replace(".","")}')
                    if cnt > 0:
                        print(f"  selector hit: {selector} → {cnt} 個")
                # company anchor 候補
                m = re.findall(r'<a[^>]+(?:class="[^"]*?(?:company|corp|client)[^"]*?")[^>]*>([^<]{3,60})</a>', content)
                if m:
                    print(f"  company-like links: {len(m)}")
                    for s in m[:5]:
                        print(f"    {s.strip()}")
            except Exception as e:
                print(f"[ERR] {url}: {e}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
