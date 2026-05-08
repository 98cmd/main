"""求人ボックスの /api/source-site-name-list で全提携媒体を取得する。

ネットワーク観察で見つかった内部 API。提携している媒体一覧 (id → 媒体名) が
取得可能。これで有名媒体との照合が可能になる。
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


async def main():
    out = Path("output/source_sites")
    out.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, locale="ja-JP")
        page = await ctx.new_page()
        # 同一オリジンになるようまずトップへ
        await page.goto("https://xn--pckua2a7gp15o89zb.com/", wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(1500)
        # API call (POST 形式で叩いていた)
        data = await page.evaluate("""
            async () => {
                const r = await fetch('/api/source-site-name-list', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
                });
                if (!r.ok) return {error: 'http_' + r.status};
                try { return await r.json(); } catch(e) { return {error: e.toString()}; }
            }
        """)
        await browser.close()

    (out / "raw.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if isinstance(data, dict) and "error" in data:
        print("ERROR:", data["error"])
        return

    # dict（id→name）想定
    print(f"提携媒体数: {len(data)}")
    items = sorted(data.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0)
    print("--- 全媒体 ---")
    for k, v in items:
        print(f"  {k:>6}: {v}")

    # 有名媒体チェック
    famous = [
        "doda", "ＤＯＤＡ", "DODA", "デューダ",
        "マイナビ", "mynavi",
        "リクナビ", "rikunabi",
        "en", "エン", "エン転職", "en転職", "en-japan",
        "ビズリーチ", "BizReach",
        "Wantedly", "ウォンテッドリー",
        "type", "Type", "TYPE",
        "Green", "green",
        "find job", "find-job", "Findjob",
        "forkwell", "Forkwell",
        "LinkedIn", "linkedin",
        "Indeed", "indeed",
        "Re就活", "re就活",
        "ジョブメドレー", "jobmedley",
        "AMBI", "ambi",
    ]
    print()
    print("--- 有名媒体マッチ ---")
    for f in famous:
        for k, v in data.items():
            if f.lower() in str(v).lower():
                print(f"  HIT: '{f}' in {k}={v}")
                break

if __name__ == "__main__":
    asyncio.run(main())
