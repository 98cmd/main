"""マイナビ転職の検索結果構造を調査する。"""
from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def fetch(url: str) -> bytes:
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
    })
    with urlopen(req, timeout=20) as r:
        return r.read()


def main():
    out = Path("output/mynavi_debug")
    out.mkdir(parents=True, exist_ok=True)

    urls = [
        # トップ
        "https://tenshoku.mynavi.jp/",
        # 全体検索リスト
        "https://tenshoku.mynavi.jp/list/",
        # ページ 2 確認
        "https://tenshoku.mynavi.jp/list/pg2/",
    ]
    for url in urls:
        try:
            html = fetch(url).decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[ERR] {url}: {e}")
            continue
        (out / f"page_{url.replace('/','_').replace(':','')[-30:]}.html").write_text(html, encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else "?"
        print(f"--- {url} ---")
        print(f"  title: {title}")
        # 求人カード候補: data-* / class 名でよく使われるもの
        cands = {}
        for sel in [
            "div.cassetteRecruit",
            "article.cassetteRecruit",
            "li.cassetteRecruit",
            "div[class*=cassette]",
            "li[class*=cassette]",
            "div[class*=jobOffer]",
            "div[class*=jobList]",
            "div[class*=companyBox]",
            "h3 a", "h2 a",
        ]:
            cnt = len(soup.select(sel))
            if cnt:
                cands[sel] = cnt
        for s, c in sorted(cands.items(), key=lambda x: -x[1])[:10]:
            print(f"  match: {s}  →  {c}")
        # URL パターン (job_/co_ 等)
        hrefs = [a.get("href", "") for a in soup.select("a[href]")]
        sample_hrefs = sorted(set(h for h in hrefs if "/job/" in h or "/co/" in h or "/coj_" in h or "/cnt_" in h))[:8]
        print(f"  sample job/co hrefs: {sample_hrefs}")
        # 会社名らしき要素
        company_like = soup.select(".companyName, .corp_name, [class*=companyName], [class*=corpName]")
        print(f"  companyName-like elements: {len(company_like)}")
        if company_like:
            for el in company_like[:5]:
                print(f"    text: {el.get_text(strip=True)[:50]!r}")
        # 1 ページ目の cassetteRecruit を 1 件詳細ダンプ
        if "list" in url and "pg2" not in url:
            cards = soup.select("div.cassetteRecruit")
            if cards:
                first = cards[0]
                print("  --- cassetteRecruit[0] all classes & sample text ---")
                # 内部の主要要素 class 一覧
                cls_set: set[str] = set()
                for tag in first.find_all(True):
                    cls = tag.get("class") or []
                    cls_set.update(cls)
                print(f"    inner classes (sample): {sorted(cls_set)[:25]}")
                # 子の主要 text
                for el in first.find_all(["a", "h2", "h3", "p"], limit=15):
                    txt = el.get_text(strip=True)[:60]
                    href = el.get("href") or ""
                    if txt:
                        print(f"    [{el.name}] href={href[:60]!r} text={txt!r}")
        print()


if __name__ == "__main__":
    main()
