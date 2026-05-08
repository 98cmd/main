from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import AsyncIterator
from urllib.parse import quote

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext

log = logging.getLogger(__name__)

KYUJINBOX_BASE = "https://xn--pckua2a7gp15o89zb.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


@dataclass
class FetchedPage:
    url: str
    cleaned_html: str


def _strip_html(raw_html: str, max_len: int = 180_000) -> str:
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
