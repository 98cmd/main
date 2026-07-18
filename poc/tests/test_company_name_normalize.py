"""会社名重複排除キー正規化のオフライン単体テスト。"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import _normalize_company_name


class NormalizeCompanyNameTest(unittest.TestCase):
    def test_strips_outer_whitespace(self):
        self.assertEqual(_normalize_company_name("  株式会社A  "), "株式会社A")

    def test_collapse_inner_whitespace(self):
        self.assertEqual(_normalize_company_name("株式会社A   B"), "株式会社A B")

    def test_full_to_half_space(self):
        # NFKC で全角空白は半角空白に
        self.assertEqual(
            _normalize_company_name("クックビズ株式会社　人材紹介窓口"),
            "クックビズ株式会社 人材紹介窓口",
        )

    def test_full_alphanumeric_to_half(self):
        self.assertEqual(_normalize_company_name("ＮＫＹ株式会社"), "NKY株式会社")

    def test_empty_input(self):
        self.assertEqual(_normalize_company_name(""), "")
        self.assertEqual(_normalize_company_name(None), "")

    def test_consecutive_internal_full_and_half_spaces(self):
        self.assertEqual(_normalize_company_name("A　 　B"), "A B")


if __name__ == "__main__":
    unittest.main()
