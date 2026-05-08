"""厚労省 人材サービス総合サイト（jinzai.hellowork.mhlw.go.jp）での会社名検索。

求人ボックス detail で取れない license_number / 住所 / 電話番号を補完するための公的データソース。
公開・公的サイトなので法務リスク低い。アクセス間隔を 3 秒以上空ける。

3 段階画面遷移:
  1. GICB101010 (params=1: 紹介 / params=0: 派遣) → 1段目クリック
  2. GICB102030.do or GICB102010.do (詳細条件画面) → nm_btnOk クリック
  3. GICB102060.do or GICB102050.do (検索フォーム画面) → 全国チェック + 会社名 + nm_btnSearch[1] クリック
  → 結果ページ
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, asdict
from typing import Any

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext

log = logging.getLogger(__name__)

MHLW_BASE = "https://jinzai.hellowork.mhlw.go.jp"
INIT_SHOUKAI = f"{MHLW_BASE}/JinzaiWeb/GICB101010.do?action=transition&screenId=GICB101010&params=1"
INIT_HAKEN = f"{MHLW_BASE}/JinzaiWeb/GICB101010.do?action=transition&screenId=GICB101010&params=0"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


@dataclass
class MHLWBusiness:
    kind: str  # "shoukai" / "haken"
    license_number: str
    license_date: str
    operator_name: str
    business_name: str
    address: str
    phone: str

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


class MHLWLookup:
    def __init__(self, access_delay: float = 3.0, headless: bool = True):
        self.access_delay = access_delay
        self.headless = headless
        self._browser: Browser | None = None
        self._ctx: BrowserContext | None = None
        self._pw = None

    async def __aenter__(self) -> "MHLWLookup":
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._ctx = await self._browser.new_context(
            user_agent=UA,
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
            extra_http_headers={"Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8"},
        )
        await self._ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        return self

    async def __aexit__(self, *exc):
        if self._ctx:
            await self._ctx.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def lookup(self, operator_name: str) -> dict[str, list[MHLWBusiness]]:
        """会社名で紹介・派遣両方を検索。{'shoukai': [...], 'haken': [...]} を返す。"""
        out: dict[str, list[MHLWBusiness]] = {"shoukai": [], "haken": []}
        for kind, init_url in [("shoukai", INIT_SHOUKAI), ("haken", INIT_HAKEN)]:
            try:
                items = await self._search(kind, init_url, operator_name)
                out[kind] = items
                log.info("MHLW %s '%s' → %d hits", kind, operator_name, len(items))
            except Exception as exc:
                log.warning("MHLW %s '%s' failed: %s", kind, operator_name, exc)
            await asyncio.sleep(self.access_delay)
        return out

    async def _search(self, kind: str, init_url: str, operator_name: str) -> list[MHLWBusiness]:
        assert self._ctx is not None
        page = await self._ctx.new_page()
        try:
            # step1
            await page.goto(init_url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(800)
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                await page.locator('input[name="nm_btnSearch"]').first.click()
            await page.wait_for_timeout(800)

            # step2: 詳細条件画面の OK ボタン
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                await page.locator('input[name="nm_btnOk"]').first.click()
            await page.wait_for_timeout(800)

            # step3: 全国 + 会社名 + 検索
            zenkoku = page.locator('input[name="cbZenkoku"]').first
            try:
                if await zenkoku.is_visible():
                    if not await zenkoku.is_checked():
                        await zenkoku.check()
            except Exception:
                pass
            await page.locator('input[name="txtJigyonushiName"]').fill(operator_name)
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                await page.locator('input[name="nm_btnSearch"]').nth(1).click()
            await page.wait_for_timeout(1500)

            html = await page.content()
            return self._parse(html, kind)
        finally:
            await page.close()

    @staticmethod
    def _parse(html: str, kind: str) -> list[MHLWBusiness]:
        """結果ページから事業所一覧を抽出。span#ID_lb* を index 順に zip する。"""
        soup = BeautifulSoup(html, "html.parser")
        nos = [s.get_text(strip=True) for s in soup.select('span#ID_lbKyokatodokedeNo')]
        dates = [s.get_text(strip=True) for s in soup.select('span#ID_lbKyokatodokedeDate')]
        operators = [s.get_text(strip=True) for s in soup.select('span#ID_lbJigyonushiName')]
        bnames = [s.get_text(strip=True) for s in soup.select('span#ID_lbJigyoshoName')]
        addrs = [s.get_text(strip=True) for s in soup.select('span#ID_lbJigyoshoAddress')]
        phones = [s.get_text(strip=True) for s in soup.select('span#ID_lbTel')]
        n = min(len(nos), len(dates), len(operators), len(bnames), len(addrs), len(phones))
        out = []
        for i in range(n):
            out.append(MHLWBusiness(
                kind=kind,
                license_number=nos[i],
                license_date=dates[i],
                operator_name=operators[i],
                business_name=bnames[i],
                address=addrs[i],
                phone=phones[i],
            ))
        return out


def pick_primary(matches: list[MHLWBusiness], target_name: str) -> MHLWBusiness | None:
    """事業所リストから「補完用の代表 1 件」を選ぶ。

    優先: 事業主名 == 事業所名（＝本社）かつ事業主名 と target_name が部分一致 → 先頭から
    フォールバック: target_name が事業主名に部分一致する最初の項目
    """
    target = target_name.strip()
    if not matches:
        return None
    # 1. 本社っぽい行（operator == business name）かつ部分一致
    for m in matches:
        if m.operator_name == m.business_name and target and target in m.operator_name:
            return m
    # 2. 部分一致するもの
    for m in matches:
        if target and target in m.operator_name:
            return m
    return matches[0]
