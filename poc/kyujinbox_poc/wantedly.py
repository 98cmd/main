"""Wantedly から会社名 + 求人 URL を抽出する。

2 段構成で母集団を確保する:
  Phase 1: /projects + フィルタ URL の Apollo state (Next.js SSR) から取得。
           active 求人タイトル付き。会社単位で重複排除すると 16〜20 社程度しか取れない。
  Phase 2: sitemap (sitemap1〜N.xml.gz) から /companies/<slug> を抽出し、
           各社の HTML title から会社名を取得。100 社到達まで補完。

抽出対象（Phase 1）:
    state[ 'JobPost:{"id":"..."}' ] = {title, company: {__ref: 'Company:<id>'}}
    state[ 'Company:<id>' ] = {name, ...}

抽出対象（Phase 2）:
    https://www.wantedly.com/sitemaps/sitemap.xml.gz (index)
      → sitemap1.xml.gz, sitemap2.xml.gz, ...
      → /companies/<slug> URL を抽出
      → 各 /companies/<slug> の <title> = "<会社名>の会社情報 - Wantedly"
"""
from __future__ import annotations
import gzip
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
SITEMAP_INDEX_URL = f"{WANTEDLY_BASE}/sitemaps/sitemap.xml.gz"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
COMPANY_TITLE_RE = re.compile(r"^(.+?)の会社情報\s*-\s*Wantedly\s*$")


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


def _fetch_gz(url: str, timeout: float = 30.0) -> str:
    """gzip 圧縮 sitemap を取得。"""
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept-Encoding": "gzip",
    })
    with urlopen(req, timeout=timeout) as r:
        return gzip.decompress(r.read()).decode("utf-8", errors="ignore")


def _list_sitemaps() -> list[str]:
    """sitemap index を取得して個別 sitemap URL を返す。"""
    xml = _fetch_gz(SITEMAP_INDEX_URL)
    return re.findall(r"<loc>(https://www\.wantedly\.com/sitemaps/sitemap\d+\.xml\.gz)</loc>", xml)


def _extract_company_slugs(sitemap_xml: str) -> list[str]:
    """sitemap XML から /companies/<slug> の slug を順序維持・重複排除して抽出。"""
    locs = re.findall(r"<loc>(https://www\.wantedly\.com/companies/[^<]+)</loc>", sitemap_xml)
    seen: set[str] = set()
    out: list[str] = []
    for u in locs:
        m = re.search(r"/companies/([^/?#]+)", u)
        if not m:
            continue
        slug = m.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        out.append(slug)
    return out


def _fetch_company_name(slug: str, timeout: float = 20.0) -> str | None:
    """/companies/<slug> の HTML title から会社名を抽出。

    title 形式: "<会社名>の会社情報 - Wantedly"
    退会・非公開・形式違反は None を返す。
    """
    url = f"{WANTEDLY_BASE}/companies/{slug}"
    try:
        html = _fetch(url, timeout)
    except Exception as e:
        log.warning("fetch company page failed %s: %s", slug, e)
        return None
    soup = BeautifulSoup(html, "html.parser")
    if not soup.title or not soup.title.string:
        return None
    title = soup.title.get_text(strip=True)
    m = COMPANY_TITLE_RE.match(title)
    if not m:
        return None
    name = m.group(1).strip()
    return name or None


def _fetch_via_projects(max_companies: int, access_delay: float, max_pages: int,
                       seen_urls: set[str], seen_companies: set[str]) -> list[WantedlyListing]:
    """Phase 1: /projects + フィルタ URL を Apollo state ベースで巡回。"""
    candidates = [
        "/projects",
        "/projects?status=mid_career",
        "/projects?occupation_id=1",   # ITエンジニア
        "/projects?occupation_id=3",   # サンプル多様性のため id=3 を追加
        "/projects?occupation_id=4",   # 営業
        "/projects?occupation_id=5",   # マーケティング
        "/projects?occupation_id=6",   # 経営
        "/projects?occupation_id=8",   # デザイナー
        "/projects?occupation_id=11",  # その他
        "/projects?status=intern",
        "/projects?type=new_graduate",
    ]
    out: list[WantedlyListing] = []
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


def _fetch_via_sitemap(max_companies: int, access_delay: float, max_sitemaps: int,
                      seen_companies: set[str]) -> list[WantedlyListing]:
    """Phase 2: sitemap1〜N.xml.gz から /companies/<slug> を巡回。"""
    out: list[WantedlyListing] = []
    try:
        sitemaps = _list_sitemaps()
    except Exception as e:
        log.warning("sitemap index fetch failed: %s", e)
        return out
    log.info("sitemap index: %d sitemaps available", len(sitemaps))

    seen_slugs: set[str] = set()
    for sm_idx, sm_url in enumerate(sitemaps[:max_sitemaps], 1):
        if len(out) >= max_companies:
            break
        log.info("sitemap %d/%d: %s", sm_idx, min(len(sitemaps), max_sitemaps), sm_url)
        try:
            xml = _fetch_gz(sm_url)
        except Exception as e:
            log.warning("sitemap fetch failed %s: %s", sm_url, e)
            continue
        slugs = _extract_company_slugs(xml)
        new_slugs = [s for s in slugs if s not in seen_slugs]
        seen_slugs.update(new_slugs)
        log.info("  → %d new company slugs (cumulative %d)", len(new_slugs), len(seen_slugs))

        for slug in new_slugs:
            if len(out) >= max_companies:
                break
            co_name = _fetch_company_name(slug)
            time.sleep(access_delay)
            if not co_name:
                continue
            key = _norm(co_name)
            if not key or key in seen_companies:
                continue
            seen_companies.add(key)
            out.append(WantedlyListing(
                company_name=co_name,
                job_title="",  # sitemap 由来は求人タイトル不明（cross_filter は会社名のみ使用）
                job_url=f"{WANTEDLY_BASE}/companies/{slug}",
                source_page=900 + sm_idx,
            ))
            log.info("  [sitemap %d/%d] %s", len(out), max_companies, co_name)
    return out


def fetch_listings(max_companies: int = 100, access_delay: float = 5.0,
                   max_pages: int = 8, use_sitemap: bool = True,
                   max_sitemaps: int = 5) -> list[WantedlyListing]:
    """Wantedly から会社名一覧を取得。

    Phase 1 (/projects 巡回) で取れる active 求人保有会社を優先し、
    Phase 2 (sitemap 巡回) で残りを補完する。
    """
    out: list[WantedlyListing] = []
    seen_urls: set[str] = set()
    seen_companies: set[str] = set()

    log.info("phase 1: /projects + フィルタ URL 巡回 (max=%d)", max_companies)
    out.extend(_fetch_via_projects(max_companies, access_delay, max_pages, seen_urls, seen_companies))
    log.info("phase 1 done: %d companies", len(out))

    if use_sitemap and len(out) < max_companies:
        remaining = max_companies - len(out)
        log.info("phase 2: sitemap 巡回で %d 社補完 (max_sitemaps=%d)", remaining, max_sitemaps)
        out.extend(_fetch_via_sitemap(remaining, access_delay, max_sitemaps, seen_companies))
        log.info("phase 2 done: total %d companies", len(out))

    return out
