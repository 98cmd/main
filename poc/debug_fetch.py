"""デバッグ: 求人ボックス検索ページの取得結果を保存して中身を確認する。"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from kyujinbox_poc.scraper import KyujinboxScraper, _strip_html
from playwright.async_api import async_playwright

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

async def main():
    out = Path("output/debug")
    out.mkdir(parents=True, exist_ok=True)

    url = "https://xn--pckua2a7gp15o89zb.com/?e=%E4%BA%BA%E6%9D%90%E7%B4%B9%E4%BB%8B%20%E8%A3%BD%E9%80%A0"
    print(f"target: {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=USER_AGENT, locale="ja-JP")
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(3000)

        final_url = page.url
        title = await page.title()
        raw = await page.content()
        text = await page.evaluate("() => document.body.innerText")

        (out / "raw.html").write_text(raw, encoding="utf-8")
        (out / "stripped.html").write_text(_strip_html(raw), encoding="utf-8")
        (out / "innertext.txt").write_text(text, encoding="utf-8")
        (out / "meta.txt").write_text(
            f"final_url: {final_url}\ntitle: {title}\nraw_len: {len(raw)}\ntext_len: {len(text)}\n",
            encoding="utf-8",
        )

        await browser.close()

    print(f"saved: {out}")
    print(f"final_url: {final_url}")
    print(f"title: {title}")
    print(f"raw_len: {len(raw)}, text_len: {len(text)}")

if __name__ == "__main__":
    asyncio.run(main())
