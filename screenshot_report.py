"""デプロイ済みレポートを Playwright で full-page screenshot する。

出力:
  client_report/screenshots/report_summary.png  (index.html フルページ)
  client_report/screenshots/report_messages.png (messages.html フルページ)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright


REPO_ROOT = Path(__file__).resolve().parent
OUT_DIR = REPO_ROOT / "client_report" / "screenshots"


async def shoot(url: str, out_path: Path, viewport_width: int = 1280) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": viewport_width, "height": 900},
            device_scale_factor=2,
            locale="ja-JP",
        )
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=60_000)
        await page.wait_for_timeout(800)  # font/SVG 安定化
        await page.screenshot(path=str(out_path), full_page=True, type="png")
        await browser.close()


async def main_async(base_url: str) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = [
        (f"{base_url.rstrip('/')}/", OUT_DIR / "report_summary.png"),
        (f"{base_url.rstrip('/')}/messages.html", OUT_DIR / "report_messages.png"),
    ]
    for url, out in targets:
        print(f"shooting {url} → {out.name}")
        await shoot(url, out)
        print(f"  size: {out.stat().st_size // 1024} KB")
    print("done")
    return 0


def main() -> int:
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://kyujinbox-client-report-skuwahara-6605s-projects.vercel.app"
    return asyncio.run(main_async(url))


if __name__ == "__main__":
    raise SystemExit(main())
