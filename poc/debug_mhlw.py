"""厚労省 人材サービス総合サイトの検索 URL 構造を調査。"""
from __future__ import annotations
import asyncio
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
TOP = "https://jinzai.hellowork.mhlw.go.jp/"
TEST_COMPANY = "株式会社プレックス"

async def main():
    out = Path("output/mhlw_debug")
    out.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=UA,
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
            },
        )
        # webdriver/automation flag を消す
        await ctx.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['ja-JP', 'ja', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            """
        )
        page = await ctx.new_page()

        # 検索アクション URL を試す
        urls = [
            "https://jinzai.hellowork.mhlw.go.jp/JinzaiWeb/GICB101010.do?action=initDisp&screenId=GICB101010",
            "https://jinzai.hellowork.mhlw.go.jp/JinzaiWeb/GICB101010.do?action=transition&screenId=GICB101010&params=0",
            "https://jinzai.hellowork.mhlw.go.jp/JinzaiWeb/GICB101010.do?action=transition&screenId=GICB101010&params=1",
        ]
        for i, u in enumerate(urls):
            try:
                resp = await page.goto(u, wait_until="domcontentloaded", timeout=20_000)
                await page.wait_for_timeout(1500)
                status = resp.status if resp else "?"
                title = await page.title()
                print(f"[{status}] {u} -> title={title!r}")
                if status == 200:
                    (out / f"page_{i}.html").write_text(
                        await page.content(), encoding="utf-8"
                    )
                    # form, input, hidden を抜き出してメモ
                    forms = await page.locator("form").all()
                    summary = [f"forms_count: {len(forms)}"]
                    for fi, f in enumerate(forms):
                        action = await f.get_attribute("action")
                        method = await f.get_attribute("method")
                        summary.append(f"  form#{fi} action={action} method={method}")
                        inputs = await f.locator("input,select,textarea").all()
                        for inp in inputs:
                            n = await inp.get_attribute("name")
                            t = await inp.get_attribute("type")
                            v = await inp.get_attribute("value")
                            ph = await inp.get_attribute("placeholder")
                            if n:
                                summary.append(f"    {t or '?'}:{n} value={v!r} ph={ph!r}")
                    (out / f"page_{i}_form.txt").write_text("\n".join(summary), encoding="utf-8")
                    print(f"  saved: page_{i}.html (form summary in page_{i}_form.txt)")
            except Exception as e:
                print(f"[ERR] {u} -> {e}")
            await page.wait_for_timeout(1500)
        return

        # 2. リンク一覧（事業所検索系を探す）
        links = await page.locator("a").all()
        link_summary = []
        for a in links[:80]:
            href = await a.get_attribute("href") or ""
            text = (await a.inner_text() or "").strip()[:50]
            if href and (("事業所" in text) or ("検索" in text) or ("紹介" in text) or ("派遣" in text) or ("search" in href.lower())):
                link_summary.append(f"{text} -> {href}")
        (out / "links.txt").write_text("\n".join(link_summary), encoding="utf-8")
        print(f"--- candidate links ({len(link_summary)}) ---")
        for l in link_summary[:30]:
            print(l)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
