"""デバッグ: 求人ボックスの XHR/fetch 通信を全キャプチャ → 内部 API 候補を抽出。
ログインなしで検索結果ページを開き、ブラウザが裏で叩く JSON エンドポイントを探す。
"""
from __future__ import annotations
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
BASE = "https://xn--pckua2a7gp15o89zb.com"
TARGETS = [
    f"{BASE}/",
    f"{BASE}/%E4%BA%BA%E6%9D%90%E7%B4%B9%E4%BB%8B-%E8%A3%BD%E9%80%A0%E3%81%AE%E4%BB%95%E4%BA%8B",
]

async def main():
    out = Path("output/network")
    out.mkdir(parents=True, exist_ok=True)

    requests_log: list[dict] = []
    api_responses: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, locale="ja-JP")
        page = await ctx.new_page()

        async def on_response(resp):
            try:
                url = resp.url
                ct = (resp.headers.get("content-type") or "").lower()
                method = resp.request.method
                rtype = resp.request.resource_type
                # JSON / API っぽいものだけ詳細キャプチャ
                if "json" in ct or rtype in ("xhr", "fetch") or "/api" in url or "/graphql" in url or url.endswith(".json"):
                    body_text = ""
                    try:
                        if "json" in ct or url.endswith(".json"):
                            body_text = await resp.text()
                            if len(body_text) > 4000:
                                body_text = body_text[:4000] + "...(truncated)"
                    except Exception:
                        body_text = "(failed to read body)"
                    api_responses.append({
                        "url": url,
                        "method": method,
                        "status": resp.status,
                        "type": rtype,
                        "content_type": ct,
                        "body_preview": body_text,
                    })
                requests_log.append({
                    "url": url, "method": method, "type": rtype,
                    "status": resp.status, "ct": ct,
                })
            except Exception as e:
                requests_log.append({"err": str(e), "url": getattr(resp, "url", "?")})

        page.on("response", lambda r: asyncio.create_task(on_response(r)))

        for tgt in TARGETS:
            print(f"=== visiting {tgt} ===")
            try:
                await page.goto(tgt, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_timeout(4000)  # XHR が走り切るのを待つ
            except Exception as e:
                print(f"navigation error: {e}")
            await asyncio.sleep(2)

        await browser.close()

    (out / "all_requests.json").write_text(
        json.dumps(requests_log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "api_responses.json").write_text(
        json.dumps(api_responses, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # サマリ
    same_origin = [r for r in requests_log if BASE in r.get("url", "")]
    print(f"total requests: {len(requests_log)}")
    print(f"same-origin: {len(same_origin)}")
    print(f"api-like responses (json/xhr/fetch/api/graphql): {len(api_responses)}")
    # ユニーク path のうち kyujinbox 内のもの
    paths = sorted({urlparse(r["url"]).path for r in same_origin if "url" in r})
    print("--- same-origin unique paths ---")
    for p_ in paths[:60]:
        print(p_)

if __name__ == "__main__":
    asyncio.run(main())
