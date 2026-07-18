"""求人ボックス「人材紹介 製造」のヒット件数とページ上限を確認する。"""
from __future__ import annotations
import asyncio
import re
import sys
from bs4 import BeautifulSoup
from kyujinbox_poc.scraper import KyujinboxScraper

QUERY = "人材紹介 製造"

async def main():
    async with KyujinboxScraper(access_delay=2.0) as s:
        # 1 ページ目
        page1 = await s.fetch_search(QUERY, 1)
        html1 = page1.cleaned_html
        print(f"=== page 1 ({s.search_url(QUERY, 1)}) ===")
        # 件数候補
        cnt_patterns = [
            r"検索結果\s*([0-9,]+)\s*件",
            r"([0-9,]+)\s*件中",
            r"([0-9,]+)\s*件\s*本日の新着",
            r"<title>[^<]*?([0-9,]+)\s*件",
        ]
        for p in cnt_patterns:
            m = re.search(p, html1)
            if m:
                print(f"  match {p!r}: {m.group(1)}")
        # pagination リンクから最大ページ
        soup = BeautifulSoup(html1, "html.parser")
        max_page = 1
        for a in soup.select('a[href]'):
            m = re.search(r"pg=(\d+)", a.get("href", ""))
            if m:
                max_page = max(max_page, int(m.group(1)))
        print(f"  pagination links max page: {max_page}")

        # 試しに max_page + 1 と 99 にアクセスして挙動確認
        for try_page in [max_page, max_page + 1, 50, 99, 100]:
            try:
                p = await s.fetch_search(QUERY, try_page)
                # listing が含まれてるか軽く判定
                soup_p = BeautifulSoup(p.cleaned_html, "html.parser")
                cards = soup_p.select('a[href*="/jb/"]')
                title_match = re.search(r"<title>([^<]+)</title>", p.cleaned_html)
                title = title_match.group(1) if title_match else "?"
                # 「該当なし」「件中」も確認
                no_hit = "該当する求人はありません" in p.cleaned_html or "該当する求人が見つかりません" in p.cleaned_html
                print(f"  page {try_page:>3}: jb_links={len(cards)} no_hit={no_hit} title={title[:50]!r}")
            except Exception as e:
                print(f"  page {try_page:>3}: ERR {e}")

if __name__ == "__main__":
    asyncio.run(main())
