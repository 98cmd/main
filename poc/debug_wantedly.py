"""Wantedly /projects の構造を調査する。"""
from __future__ import annotations
import re
from pathlib import Path
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
    out = Path("output/wantedly_debug")
    out.mkdir(parents=True, exist_ok=True)

    urls = [
        "https://www.wantedly.com/projects",
        "https://www.wantedly.com/projects?page=2",
        "https://www.wantedly.com/projects?status=mid_career",
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
        print(f"  html len: {len(html)}")
        # 求人カード候補
        for sel in ["[class*=Project]", "[class*=Card]", "article", "[data-test*=project]"]:
            cnt = len(soup.select(sel))
            if 3 <= cnt <= 200:
                print(f"  match {sel}: {cnt}")
        # /projects/<id>/ や /companies/<slug>/ のリンク数
        proj_links = [a.get("href","") for a in soup.select("a[href*='/projects/']")]
        comp_links = [a.get("href","") for a in soup.select("a[href*='/companies/']")]
        print(f"  /projects/ anchors: {len(proj_links)}")
        print(f"  /companies/ anchors: {len(comp_links)}")
        # __NEXT_DATA__ がある (Next.js SSR)
        nxt = soup.select_one("script#__NEXT_DATA__")
        if nxt:
            txt = nxt.get_text(strip=True)
            print(f"  __NEXT_DATA__: {len(txt)} bytes (Next.js SSR)")
            # company / name のキーが何個あるか
            for k in ["\"name\":", "\"company_name\":", "\"company\":", "\"title\":"]:
                print(f"    {k!r}: {txt.count(k)} 回")
        # カード内の見出しサンプル
        h_samples = []
        for h in soup.select("h2, h3"):
            t = h.get_text(strip=True)
            if t:
                h_samples.append(t[:50])
        print(f"  h2/h3 sample: {h_samples[:5]}")
        print()


if __name__ == "__main__":
    main()
