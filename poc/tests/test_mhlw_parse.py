"""MHLW 結果パースのオフライン単体テスト。サンプル HTML のみで API/サイト不要。"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

# poc/ をパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kyujinbox_poc.mhlw import MHLWLookup, MHLWBusiness, pick_primary

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class MHLWParseTest(unittest.TestCase):
    def test_shoukai_returns_at_least_one_business(self):
        sample = SAMPLES / "mhlw_search_shoukai.html"
        if not sample.exists():
            self.skipTest(f"sample missing: {sample}")
        html = sample.read_text(encoding="utf-8")
        items = MHLWLookup._parse(html, "shoukai")
        self.assertGreater(len(items), 0, "should parse at least 1 business from shoukai sample")
        first = items[0]
        self.assertIsInstance(first, MHLWBusiness)
        self.assertEqual(first.kind, "shoukai")
        self.assertRegex(first.license_number, r"\d{2}.+\d+", "license number format")
        self.assertTrue(first.address, "address must not be empty")
        self.assertTrue(first.operator_name, "operator must not be empty")

    def test_haken_parser(self):
        sample = SAMPLES / "mhlw_search_haken.html"
        if not sample.exists():
            self.skipTest(f"sample missing: {sample}")
        html = sample.read_text(encoding="utf-8")
        items = MHLWLookup._parse(html, "haken")
        # 派遣サンプルは 0 件のこともある（テスト時の検索条件依存）
        for it in items:
            self.assertEqual(it.kind, "haken")

    def test_pick_primary_prefers_partial_match(self):
        sample = SAMPLES / "mhlw_search_shoukai.html"
        if not sample.exists():
            self.skipTest(f"sample missing: {sample}")
        items = MHLWLookup._parse(sample.read_text(encoding="utf-8"), "shoukai")
        prim = pick_primary(items, "プレックス")
        self.assertIsNotNone(prim)
        self.assertIn("プレックス", prim.operator_name)

    def test_pick_primary_empty_returns_none(self):
        self.assertIsNone(pick_primary([], "anything"))


if __name__ == "__main__":
    unittest.main()
