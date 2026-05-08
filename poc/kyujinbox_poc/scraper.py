from __future__ import annotations

import asyncio
import logging
import unicodedata
from dataclasses import dataclass
from typing import AsyncIterator, TYPE_CHECKING
from urllib.parse import quote

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext

if TYPE_CHECKING:
    from .extractor import ClaudeExtractor

log = logging.getLogger(__name__)


def _norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", (s or "").strip()).split())

KYUJINBOX_BASE = "https://xn--pckua2a7gp15o89zb.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


@dataclass
class FetchedPage:
    url: str
    cleaned_html: str


def _strip_html(raw_html: str, max_len: int = 80_000) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "header", "footer", "nav"]):
        tag.decompose()
    body = soup.body or soup
    text_blob = body.decode(formatter="minimal")
    if len(text_blob) > max_len:
        text_blob = text_blob[:max_len]
    return text_blob


class KyujinboxScraper:
    def __init__(self, access_delay: float = 5.0, headless: bool = True):
        self.access_delay = access_delay
        self.headless = headless
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._playwright = None

    async def __aenter__(self) -> "KyujinboxScraper":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(user_agent=USER_AGENT, locale="ja-JP")
        return self

    async def __aexit__(self, *exc):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _fetch(self, url: str) -> FetchedPage:
        assert self._context is not None
        page = await self._context.new_page()
        try:
            log.info("fetch %s", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(1500)
            raw = await page.content()
        finally:
            await page.close()
        return FetchedPage(url=url, cleaned_html=_strip_html(raw))

    def search_url(self, query: str, page_no: int = 1) -> str:
        # 求人ボックスはパスベース URL: /<keyword>の仕事
        # スペースはハイフン区切り、末尾「の仕事」はハイフン無しで連結
        keyword_path = quote(query.replace("　", " ").strip().replace(" ", "-"))
        base = f"{KYUJINBOX_BASE}/{keyword_path}の仕事"
        if page_no <= 1:
            return base
        return f"{base}?pg={page_no}"

    async def fetch_search(self, query: str, page_no: int = 1) -> FetchedPage:
        page = await self._fetch(self.search_url(query, page_no))
        await asyncio.sleep(self.access_delay)
        return page

    async def fetch_detail(self, url: str) -> FetchedPage:
        page = await self._fetch(url)
        await asyncio.sleep(self.access_delay)
        return page

    async def crawl(self, query: str, max_pages: int = 2) -> AsyncIterator[FetchedPage]:
        for page_no in range(1, max_pages + 1):
            yield await self.fetch_search(query, page_no)

    async def check_existence(
        self,
        company_name: str,
        extractor: "ClaudeExtractor | None" = None,
        retries: int = 2,
    ) -> tuple[bool, str, int, list[str]]:
        """会社名で求人ボックス検索 → AI 抽出で listing の company_name と一致判定。

        フリーテキスト検索だと類似名の他社が大量にヒットするため、AI で抽出した
        listing.company_name を NFKC 正規化して target と比較する。

        Returns:
            (exists, search_url, listing_count, matched_company_names)
            - exists: True なら検索結果に対象会社の listing が含まれる（出稿あり）
            - search_url: 検索 URL
            - listing_count: 抽出された listing 総数（参考）
            - matched_company_names: マッチした listing の会社名リスト（人間レビュー用）
        """
        from .extractor import ClaudeExtractor as _ClaudeExtractor

        if extractor is None:
            extractor = _ClaudeExtractor()
        url = self.search_url(company_name)

        last_exc: Exception | None = None
        page = None
        for attempt in range(retries + 1):
            try:
                page = await self._fetch(url)
                break
            except Exception as e:
                last_exc = e
                if attempt < retries:
                    await asyncio.sleep(2.0 * (attempt + 1))
                else:
                    raise
        if page is None:
            raise last_exc or RuntimeError("fetch failed")

        await asyncio.sleep(self.access_delay)
        html = page.cleaned_html

        # 明示的な「該当なし」表示なら即 False
        no_hit_markers = (
            "該当する求人がありません",
            "該当する求人が見つかりません",
            "0件中0件",
        )
        if any(m in html for m in no_hit_markers):
            return False, url, 0, []

        # AI で listing 抽出 → 会社名一致判定
        try:
            listings = extractor.extract_listings(html)
        except Exception as e:
            log.warning("extract_listings failed for %r: %s", company_name, e)
            return False, url, 0, []

        target = _norm(company_name)
        matched: list[str] = []
        for l in listings:
            cand = _norm(l.company_name)
            if not cand:
                continue
            # 完全一致 or 双方向の包含関係（営業上「同じ会社」と判定して良い範囲）
            if cand == target or target in cand or cand in target:
                matched.append(l.company_name)
        return len(matched) > 0, url, len(listings), matched
