"""Wantedly /projects から会社名 + 求人 URL を抽出する。

公開ページ。Next.js SSR で `<script id="__NEXT_DATA__">` に Apollo Client の
キャッシュ全体が JSON として埋め込まれているため、HTML パース不要で
構造化データが取れる。

抽出対象:
    state[ 'JobPost:{"id":"..."}' ] = {title, company: {__ref: 'Company:<id>'}}
    state[ 'Company:<id>' ] = {name, ...}
"""
from __future__ import annotations
import json
import logging
import re
import time
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

WANTEDLY_BASE = "https://www.wantedly.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


@dataclass
class WantedlyListing:
    company_name: str
    job_title: str
    job_url: str
    source_page: int

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def _fetch(url: str, timeout: float = 20.0) -> str:
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja-JP,ja;q=0.9",
    })
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def _norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", (s or "").strip()).split())


def _parse_next_data(html: str, source_page: int) -> list[WantedlyListing]:
    """__NEXT_DATA__ から JobPost/Company を解決し listing を返す。"""
    soup = BeautifulSoup(html, "html.parser")
    nxt = soup.select_one("script#__NEXT_DATA__")
    if not nxt or not nxt.string:
        return []
    try:
        data = json.loads(nxt.string)
    except Exception as e:
        log.warning("__NEXT_DATA__ parse failed: %s", e)
        return []
    try:
        state = data["props"]["pageProps"]["__apollo"]["graphqlGatewayInitialState"]
    except KeyError:
        return []

    out: list[WantedlyListing] = []
    for key, val in state.items():
        if not key.startswith("JobPost:") or not isinstance(val, dict):
            continue
        title = val.get("title") or ""
        comp = val.get("company")
        name = ""
        if isinstance(comp, dict):
            if "__ref" in comp:
                ref = comp["__ref"]
                comp_obj = state.get(ref, {})
                if isinstance(comp_obj, dict):
                    name = comp_obj.get("name") or ""
            else:
                name = comp.get("name") or ""
        if not name:
            continue
        # JobPost:{"id":"1743580"} から id 抽出
        m = re.search(r'"id"\s*:\s*"(\d+)"', key)
        job_id = m.group(1) if m else ""
        job_url = f"{WANTEDLY_BASE}/projects/{job_id}" if job_id else ""
        out.append(WantedlyListing(
            company_name=name.strip(),
            job_title=title.strip(),
            job_url=job_url,
            source_page=source_page,
        ))
    return out


def fetch_listings(max_companies: int = 100, access_delay: float = 5.0,
                   max_pages: int = 8) -> list[WantedlyListing]:
    """Wantedly /projects から会社名一覧を取得。

    /projects はページネーションが効きにくいため、複数のフィルタ URL を
    巡回してリスト多様性を確保する。
    """
    # フィルタ・カテゴリで多様な listing を集める
    candidates = [
        "/projects",
        "/projects?status=mid_career",
        "/projects?occupation_id=1",   # ITエンジニア
        "/projects?occupation_id=4",   # 営業
        "/projects?occupation_id=5",   # マーケティング
        "/projects?occupation_id=6",   # 経営
        "/projects?occupation_id=8",   # デザイナー
        "/projects?occupation_id=11",  # その他
        "/projects?status=intern",
        "/projects?type=new_graduate",
    ]
    out: list[WantedlyListing] = []
    seen_urls: set[str] = set()
    seen_companies: set[str] = set()
    for page_no, path in enumerate(candidates, 1):
        if len(out) >= max_companies or page_no > max_pages:
            break
        url = WANTEDLY_BASE + path
        log.info("fetch wantedly: %s", url)
        try:
            html = _fetch(url)
        except Exception as e:
            log.warning("fetch failed %s: %s", url, e)
            time.sleep(access_delay)
            continue
        items = _parse_next_data(html, page_no)
        log.info("  page %d: %d items", page_no, len(items))
        for it in items:
            if len(out) >= max_companies:
                break
            if it.job_url in seen_urls:
                continue
            seen_urls.add(it.job_url)
            key = _norm(it.company_name)
            if not key or key in seen_companies:
                continue
            seen_companies.add(key)
            out.append(it)
        time.sleep(access_delay)
    return out
