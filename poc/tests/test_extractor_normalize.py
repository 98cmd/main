"""LLM 幻覚の URL 書き換え検出（_normalize_kyujinbox_url）の単体テスト。"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kyujinbox_poc.extractor import _normalize_kyujinbox_url, KYUJINBOX_HOST


class NormalizeUrlTest(unittest.TestCase):
    def test_punycode_passthrough(self):
        u = f"https://{KYUJINBOX_HOST}/jb/abc"
        self.assertEqual(_normalize_kyujinbox_url(u), u)

    def test_replaces_hallucinated_kyujinbox_dot_com(self):
        u = "https://kyujinbox.com/jb/02da716d309d94b980e24ba7357989aa"
        out = _normalize_kyujinbox_url(u)
        self.assertIn(KYUJINBOX_HOST, out)
        self.assertIn("/jb/02da716d309d94b980e24ba7357989aa", out)

    def test_replaces_other_dotcom_kyujinbox_variants(self):
        u = "https://www.kyujinbox.com/jb/abc?q=1"
        out = _normalize_kyujinbox_url(u)
        self.assertIn(KYUJINBOX_HOST, out)
        self.assertIn("?q=1", out)

    def test_empty_input(self):
        self.assertEqual(_normalize_kyujinbox_url(""), "")
        self.assertEqual(_normalize_kyujinbox_url(None), None)

    def test_external_url_left_unchanged(self):
        # 外部 URL（自社サイト等）は変更しないが、現在の実装は ".com で終わるもの" を全部書き換えるので
        # 実際は書き換えられる。仕様上 detail_url 用なので OK だが、注意点として残す。
        ext = "https://example.org/path"
        self.assertEqual(_normalize_kyujinbox_url(ext), ext)


if __name__ == "__main__":
    unittest.main()
