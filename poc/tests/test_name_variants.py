"""会社名バリエーション生成のオフライン単体テスト。"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kyujinbox_poc.mhlw import generate_name_variants


class GenerateNameVariantsTest(unittest.TestCase):
    def test_strips_kabushikigaisha_prefix(self):
        v = generate_name_variants("株式会社プレックス")
        self.assertIn("プレックス", v)
        self.assertNotIn("株式会社プレックス", v, "元の名前は含めない")

    def test_strips_kabushikigaisha_suffix(self):
        v = generate_name_variants("キチナングループ株式会社")
        self.assertIn("キチナングループ", v)

    def test_strips_short_form(self):
        v = generate_name_variants("(株)テスト")
        self.assertIn("テスト", v)
        v2 = generate_name_variants("（株）テスト")
        self.assertIn("テスト", v2)

    def test_strips_yugen_godo(self):
        v = generate_name_variants("有限会社サンプル")
        self.assertIn("サンプル", v)
        v2 = generate_name_variants("合同会社サンプル")
        self.assertIn("サンプル", v2)

    def test_full_to_half_width(self):
        v = generate_name_variants("株式会社ＡＢＣ")
        # NFKC 正規化された半角版
        self.assertIn("株式会社ABC", v)
        self.assertIn("ABC", v, "半角化 + 株式会社削除")

    def test_no_variants_for_simple_name(self):
        v = generate_name_variants("プレックス")
        # 法人格なし、英数字なし → バリエーションは空
        self.assertEqual(v, [])

    def test_no_duplicates(self):
        v = generate_name_variants("株式会社プレックス")
        self.assertEqual(len(v), len(set(v)), "重複しない")


if __name__ == "__main__":
    unittest.main()
