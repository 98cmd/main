"""マイナビ転職パーサのオフライン単体テスト。

サンプル HTML 不要のミニ HTML で `_parse_cards` の動作を確認。
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kyujinbox_poc.mynavi import _parse_cards, _normalize_url


SAMPLE = """
<html><body>
<div class="cassetteRecruit">
  <h3>株式会社サンプル | 営業職募集</h3>
  <p class="cassetteRecruit__copy">未経験歓迎・週休二日</p>
  <a href="//tenshoku.mynavi.jp/jobinfo-100-1-86-1/">求人詳細を見る</a>
</div>
<div class="cassetteRecruit">
  <h3>有限会社別会社</h3>
  <p>SE 募集</p>
  <a href="/jobinfo-200-1-86-1/">詳細</a>
</div>
<div class="cassetteRecruit">
  <h3>関係ない要素</h3>
</div>
</body></html>
"""


class MynaviParseTest(unittest.TestCase):
    def test_parses_company_and_url(self):
        items = _parse_cards(SAMPLE, source_page=1)
        self.assertEqual(len(items), 2, "URL が無いカードは除外")
        self.assertEqual(items[0].company_name, "株式会社サンプル")
        self.assertEqual(items[0].source_page, 1)
        self.assertTrue(items[0].job_url.startswith("https://tenshoku.mynavi.jp/jobinfo-100"))
        self.assertEqual(items[1].company_name, "有限会社別会社")
        self.assertTrue(items[1].job_url.startswith("https://tenshoku.mynavi.jp/jobinfo-200"))

    def test_pipe_separator(self):
        html = '<div class="cassetteRecruit"><h3>会社A | キャッチ</h3><a href="/jobinfo-1/">x</a></div>'
        items = _parse_cards(html, source_page=2)
        self.assertEqual(items[0].company_name, "会社A")

    def test_no_pipe(self):
        html = '<div class="cassetteRecruit"><h3>会社B</h3><a href="/jobinfo-2/">x</a></div>'
        items = _parse_cards(html, source_page=2)
        self.assertEqual(items[0].company_name, "会社B")

    def test_normalize_url_protocol_relative(self):
        self.assertEqual(_normalize_url("//tenshoku.mynavi.jp/x/"), "https://tenshoku.mynavi.jp/x/")

    def test_normalize_url_relative(self):
        self.assertTrue(_normalize_url("/x/").endswith("/x/"))
        self.assertTrue(_normalize_url("/x/").startswith("https://tenshoku.mynavi.jp"))

    def test_normalize_url_absolute_passthrough(self):
        self.assertEqual(_normalize_url("https://example.com/"), "https://example.com/")


if __name__ == "__main__":
    unittest.main()
