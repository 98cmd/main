"""厚労省サイトで「株式会社プレックス」を検索 → 結果ページ HTML を保存。"""
from __future__ import annotations
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
SEARCH_SHOUKAI = "https://jinzai.hellowork.mhlw.go.jp/JinzaiWeb/GICB101010.do?action=transition&screenId=GICB101010&params=1"
SEARCH_HAKEN = "https://jinzai.hellowork.mhlw.go.jp/JinzaiWeb/GICB101010.do?action=transition&screenId=GICB101010&params=0"
COMPANY = "株式会社プレックス"

async def main():
    out = Path("output/mhlw_debug")
    out.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=UA, locale="ja-JP", timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
            extra_http_headers={"Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8"},
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        for kind, url in [("shoukai", SEARCH_SHOUKAI), ("haken", SEARCH_HAKEN)]:
            page = await ctx.new_page()
            try:
                print(f"=== {kind}: opening init URL ===")
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_timeout(1500)

                print(f"=== {kind}: step1 click search (空欄→詳細条件画面へ) ===")
                btn = page.locator('input[name="nm_btnSearch"]').first
                async with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                    await btn.click()
                await page.wait_for_timeout(1200)
                print(f"  -> step1 done: {page.url}")

                print(f"=== {kind}: step2 click nm_btnOk (詳細条件→検索フォーム画面) ===")
                btn2 = page.locator('input[name="nm_btnOk"]').first
                async with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                    await btn2.click()
                await page.wait_for_timeout(1500)
                print(f"  -> step2 done: {page.url}")

                # 検索フォーム画面で 全国チェック + 会社名入力 + 検索
                print(f"=== {kind}: step3 check zenkoku + fill operator + click search_button ===")
                # 全国チェック
                zenkoku = page.locator('input[name="cbZenkoku"]').first
                if await zenkoku.is_visible():
                    if not await zenkoku.is_checked():
                        await zenkoku.check()
                await page.locator('input[name="txtJigyonushiName"]').fill(COMPANY)
                btn3 = page.locator('input[name="nm_btnSearch"]').nth(1)
                async with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                    await btn3.click()
                await page.wait_for_timeout(2500)

                final_url = page.url
                title = await page.title()
                html = await page.content()
                text = await page.evaluate("() => document.body.innerText")

                (out / f"search_{kind}.html").write_text(html, encoding="utf-8")
                (out / f"search_{kind}.txt").write_text(text, encoding="utf-8")
                print(f"  url: {final_url}")
                print(f"  title: {title}")
                print(f"  html_len: {len(html)}, text_len: {len(text)}")
            except Exception as e:
                print(f"  ERR: {e}")
            finally:
                await page.close()
            await asyncio.sleep(3)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
