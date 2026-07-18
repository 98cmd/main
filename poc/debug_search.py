"""デバッグ: トップページのフォームから検索 → 遷移先と結果 HTML を確認。"""
from __future__ import annotations
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
TOP = "https://xn--pckua2a7gp15o89zb.com/"
QUERY = "人材紹介 製造"

async def main():
    out = Path("output/debug2")
    out.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, locale="ja-JP")
        page = await ctx.new_page()

        await page.goto(TOP, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(1500)

        # キーワード input を探す
        kw_input = page.locator('input[name="form[keyword]"]').first
        await kw_input.fill(QUERY)
        # Enter で submit + ナビゲーション待ち
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
            await kw_input.press("Enter")
        await page.wait_for_timeout(2000)

        url1 = page.url
        title1 = await page.title()
        raw1 = await page.content()
        text1 = await page.evaluate("() => document.body.innerText")

        (out / "search_raw.html").write_text(raw1, encoding="utf-8")
        (out / "search_innertext.txt").write_text(text1, encoding="utf-8")
        (out / "meta.txt").write_text(
            f"final_url: {url1}\ntitle: {title1}\nraw_len: {len(raw1)}\ntext_len: {len(text1)}\n",
            encoding="utf-8",
        )
        print(f"after submit url: {url1}")
        print(f"title: {title1}")
        print(f"raw_len: {len(raw1)}, text_len: {len(text1)}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
