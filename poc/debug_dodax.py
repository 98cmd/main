"""doda X の検索結果構造を調査する。"""
from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def fetch(url: str) -> str:
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja-JP,ja;q=0.9",
    })
    with urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")


def main():
    out = Path("output/dodax_debug")
    out.mkdir(parents=True, exist_ok=True)

    urls = [
        "https://doda-x.jp/job/search/",
        "https://doda-x.jp/job/search/?page=1",
        "https://doda-x.jp/jobs/oc_001/",
        "https://doda-x.jp/jobs/oc_002/",
    ]
    for i, url in enumerate(urls):
        try:
            html = fetch(url)
        except Exception as e:
            print(f"[ERR] {url}: {e}")
            continue
        (out / f"page_{i}.html").write_text(html, encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else "?"
        print(f"--- {url} ---")
        print(f"  title: {title}")
        # 会社名 / 求人カード候補
        for sel in ["[class*=Job]", "[class*=Card]", "[class*=Company]", "[class*=Result]",
                    "article", "li[class]", "div[class*=item]"]:
            cnt = len(soup.select(sel))
            if 3 <= cnt <= 100:
                print(f"  match {sel}: {cnt}")
        # JSON-LD / window.__NEXT_DATA__ 等の SPA データ
        for tag in soup.select("script[type='application/ld+json'], script#__NEXT_DATA__"):
            txt = tag.get_text(strip=True)
            if txt:
                t = txt[:120].replace("\n"," ")
                print(f"  script: {t}...")
        # 求人を含む a タグ
        sample_anchors = []
        for a in soup.select("a[href]")[:200]:
            href = a.get("href", "")
            if any(k in href for k in ["/jobs/", "/job/", "/recruitment/"]):
                txt = a.get_text(strip=True)[:50]
                sample_anchors.append((href[:90], txt))
        print(f"  job-like anchors: {len(sample_anchors)}")
        for h, t in sample_anchors[:8]:
            print(f"    {h!r}  →  {t!r}")
        print()


if __name__ == "__main__":
    main()
