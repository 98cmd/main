"""ビータスがヒット 0 件の原因調査。複数バリエーションで MHLW を叩く。"""
from __future__ import annotations
import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")

sys.path.insert(0, ".")
from kyujinbox_poc.mhlw import MHLWLookup

# main.py のフォールバックと同じ動作
if not os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ANTHROPIC_API_KEY_SCRIPTS"):
    os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY_SCRIPTS"]

VARIANTS = [
    "株式会社ビータス",
    "ビータス",
    "(株)ビータス",
    "（株）ビータス",
    "ヴィータス",
    "Beatus",
    "BEATUS",
    "ＢＥＡＴＵＳ",
    "VITAS",
]


async def main():
    async with MHLWLookup(access_delay=2.0) as m:
        for v in VARIANTS:
            try:
                res = await m.lookup(v)
                ok = len(res["shoukai"]) + len(res["haken"])
                tag = "HIT" if ok else "miss"
                print(f"[{tag:4}] {v!r:30}  shoukai={len(res['shoukai'])}, haken={len(res['haken'])}")
                if ok:
                    # 最初の 1 件をプレビュー
                    first = (res["shoukai"] + res["haken"])[0]
                    print(f"        operator={first.operator_name!r}")
                    print(f"        license={first.license_number}, address={first.address[:40]}")
            except Exception as e:
                print(f"[ERR ] {v!r}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
