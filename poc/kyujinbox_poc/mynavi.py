"""マイナビ転職の検索結果から会社名 + 求人 URL を抽出する軽量スクレイパー。

公開ページ（ログイン不要）から HTTP/1.1 の urllib で取得。Bot 対策が比較的
緩く、playwright 不要。各社カード構造:

    <div class="cassetteRecruit">
      <h3>会社名 | キャッチコピー</h3>
      <a href="//tenshoku.mynavi.jp/jobinfo-XXX/">求人詳細を見る</a>
      ...
    </div>
"""
from __future__ import annotations
import logging
import re
import time
from dataclasses import dataclass, asdict
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

MYNAVI_BASE = "https://tenshoku.mynavi.jp"
LIST_URL = f"{MYNAVI_BASE}/list/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


@dataclass
class MynaviListing:
    company_name: str
    job_title: str
    job_url: str  # 求人詳細ページ
    source_page: int  # 取得元ページ番号

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return MYNAVI_BASE + href
    return href


def _fetch(url: str, timeout: float = 20.0) -> str:
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
    })
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def _list_url(page_no: int) -> str:
    return LIST_URL if page_no <= 1 else f"{LIST_URL}pg{page_no}/"


def _parse_cards(html: str, source_page: int) -> list[MynaviListing]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[MynaviListing] = []
    for card in soup.select("div.cassetteRecruit"):
        h3 = card.select_one("h3")
        if not h3:
            continue
        h3_text = h3.get_text(strip=True)
        # 「会社名 | キャッチコピー」形式
        if "|" in h3_text:
            company, _, _catch = h3_text.partition("|")
        else:
            company = h3_text
        company = company.strip()
        # 求人タイトル候補
        title_el = card.select_one("p.cassetteRecruit__copy") or card.select_one("p")
        title = title_el.get_text(strip=True) if title_el else ""
        # 詳細 URL
        link = card.select_one("a[href*='jobinfo-']")
        job_url = _normalize_url(link.get("href", "")) if link else ""
        if not company or not job_url:
            continue
        out.append(MynaviListing(
            company_name=company,
            job_title=title,
            job_url=job_url,
            source_page=source_page,
        ))
    return out


def fetch_listings(max_companies: int = 100, access_delay: float = 5.0,
                   max_pages: int = 5) -> list[MynaviListing]:
    """マイナビ転職の検索結果から会社名一覧を取得（ページ送り対応）。"""
    out: list[MynaviListing] = []
    seen_urls: set[str] = set()
    seen_companies: set[str] = set()
    for page_no in range(1, max_pages + 1):
        if len(out) >= max_companies:
            break
        url = _list_url(page_no)
        log.info("fetch mynavi page %d: %s", page_no, url)
        try:
            html = _fetch(url)
        except Exception as e:
            log.warning("fetch failed page %d: %s", page_no, e)
            time.sleep(access_delay)
            continue
        cards = _parse_cards(html, page_no)
        log.info("  page %d: %d cards", page_no, len(cards))
        for c in cards:
            if len(out) >= max_companies:
                break
            if c.job_url in seen_urls:
                continue
            seen_urls.add(c.job_url)
            # 会社名重複排除（同社の別求人を 1 件にまとめる）
            import unicodedata
            key = " ".join(unicodedata.normalize("NFKC", c.company_name).strip().split())
            if not key or key in seen_companies:
                continue
            seen_companies.add(key)
            out.append(c)
        time.sleep(access_delay)
    return out
