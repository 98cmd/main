"""求人ボックスの完全一致検索オプションを調査する。

試行:
1. 引用符（"○○"）付き vs 引用符なしで検索結果数を比較
2. URL クエリパラメータ（&qm= や &exact= 等）の試行
3. 検索フォームの詳細検索 UI に「完全一致」オプションがあるか
"""
from __future__ import annotations
import asyncio
import re
import sys
from pathlib import Path
from urllib.parse import quote
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kyujinbox_poc.scraper import KyujinboxScraper

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


async def count_jb(html: str) -> tuple[int, str | None]:
    """jb リンク数 + 件数表示テキスト"""
    jb = len(re.findall(r"/jb/[a-zA-Z0-9_-]{8,}", html))
    rd = len(re.findall(r"/rd/\?uaid=[a-zA-Z0-9_-]+", html))
    soup = BeautifulSoup(html, "html.parser")
    # 件数: "○件中"、"検索結果 N 件" 等
    count_text = None
    for el in soup.find_all(string=re.compile(r"[0-9,]+\s*件")):
        text = str(el).strip()
        if "件中" in text or "検索結果" in text:
            count_text = text[:60]
            break
    return jb + rd, count_text


async def submit_adv_search(company: str) -> tuple[str, str]:
    """/adv/ から form[company] を入れて submit。遷移先 URL と HTML を返す。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, locale="ja-JP")
        page = await ctx.new_page()
        await page.goto("https://xn--pckua2a7gp15o89zb.com/adv/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(800)
        # form[company] にだけ入力 → submit
        await page.locator('input[name="form[company]"]').fill(company)
        # 検索ボタンを探す。class="searchBtn" 系か submit 型
        btn = page.locator('button[type=submit], input[type=submit], button:has-text("検索"), a:has-text("この条件で検索")').first
        try:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
                await btn.click()
        except Exception:
            # 直接 form を JS submit
            await page.locator('form').first.evaluate("f => f.submit()")
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)
        url = page.url
        html = await page.content()
        await browser.close()
        return url, html


async def main():
    out = Path("output/kbox_exact_debug")
    out.mkdir(parents=True, exist_ok=True)

    targets = [
        "株式会社プレックス",
        '"株式会社プレックス"',
        "「株式会社プレックス」",
        "株式会社XYZ存在しないテスト",
    ]

    print("=== /adv/ 経由で form[company] 検索 ===")
    for c in ["株式会社プレックス", "株式会社XYZ存在しないテスト", "株式会社ロピア"]:
        try:
            url, html = await submit_adv_search(c)
            jb_count = len(re.findall(r"/jb/[a-zA-Z0-9_-]{8,}", html))
            rd_count = len(re.findall(r"/rd/\?uaid=[a-zA-Z0-9_-]+", html))
            print(f"--- {c!r} ---")
            print(f"  final url: {url[:200]}")
            print(f"  jb={jb_count}, rd={rd_count}")
            # 件数表示
            soup = BeautifulSoup(html, "html.parser")
            for el in soup.find_all(string=re.compile(r"[0-9,]+\s*件")):
                t = str(el).strip()
                if "件" in t and len(t) < 40:
                    print(f"  count text: {t!r}")
                    break
            # 最初の listing カードの会社名候補
            cards = soup.select("[class*=cassette]") or soup.select("a[href*='/jb/']")
            print(f"  listing cards: {len(cards)}")
        except Exception as e:
            print(f"  ERR: {e}")
        print()

    print("=== 通常 search vs adv search 比較 ===")

    async with KyujinboxScraper(access_delay=3) as s:
        for q in targets:
            url = s.search_url(q)
            try:
                page = await s._fetch(url)
                html = page.cleaned_html
                cnt, ctext = await count_jb(html)
                print(f"--- {q!r} ---")
                print(f"  url: {url[:120]}")
                print(f"  jb+rd: {cnt}")
                print(f"  count text: {ctext!r}")
                # サンプル listing の company_name を 5 件抜く
                soup = BeautifulSoup(html, "html.parser")
                # 求人ボックスは複雑な構造、innertext から会社名を発見する
                text = soup.get_text(separator="\n", strip=True)
                # 「株式会社プレックス」という文字列が何回出るか
                target_clean = q.strip('"').strip("「").strip("」")
                occurrences = text.count(target_clean)
                print(f"  '{target_clean}' 出現回数: {occurrences}")
            except Exception as e:
                print(f"  ERR: {e}")
            print()
        # 詳細検索 UI を探す
        print("=== /adv/ 詳細条件 ===")
        page = await s._fetch("https://xn--pckua2a7gp15o89zb.com/adv/")
        # raw HTML で確認するため、別途 fetch
        soup = BeautifulSoup(page.cleaned_html, "html.parser")
        # 「完全一致」「会社名」「事業所名」関連の input/label を抽出
        for el in soup.find_all(["input", "select", "label"]):
            name = el.get("name", "") or el.get("for", "")
            txt = el.get_text(strip=True)
            placeholder = el.get("placeholder", "")
            if name or placeholder or txt:
                if any(k in (name + placeholder + txt) for k in ["会社", "企業", "完全", "exact", "事業所", "name", "company", "kw", "keyword"]):
                    print(f"  [{el.name}] name={name!r} placeholder={placeholder!r} text={txt[:40]!r}")
        # 全 input name を一覧
        print("--- all input/select names ---")
        names = sorted({(el.name, el.get("name", "")) for el in soup.find_all(["input", "select"]) if el.get("name")})
        for tag, n in names:
            print(f"  [{tag}] {n}")


if __name__ == "__main__":
    asyncio.run(main())
