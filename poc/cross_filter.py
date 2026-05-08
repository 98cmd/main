"""他媒体（マイナビ転職）→ 求人ボックス未出稿のリードリストを生成する。

フロー:
  1. マイナビ転職の検索結果から会社名 100 社を取得
  2. 各社を求人ボックスで existence check
  3. 0 件ヒット = 求人ボックス未出稿 = リード候補
  4. CSV / JSON 出力

利用例:
  ANTHROPIC_API_KEY=... python cross_filter.py --max-companies 100
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from kyujinbox_poc.extractor import ClaudeExtractor
from kyujinbox_poc.mynavi import fetch_listings as fetch_mynavi
from kyujinbox_poc.scraper import KyujinboxScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cross_filter")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="他媒体→求人ボックス未出稿リードリスト生成")
    p.add_argument("--source", choices=["mynavi"], default="mynavi", help="母集団の媒体")
    p.add_argument("--max-companies", type=int, default=100)
    p.add_argument("--mynavi-access-delay", type=float, default=5.0)
    p.add_argument("--kyujinbox-access-delay", type=float, default=5.0)
    p.add_argument("--max-source-pages", type=int, default=10)
    p.add_argument("--output-dir", default="output")
    return p.parse_args()


async def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("step 1/3: 母集団取得 (%s, max=%d)", args.source, args.max_companies)
    if args.source == "mynavi":
        listings = fetch_mynavi(
            max_companies=args.max_companies,
            access_delay=args.mynavi_access_delay,
            max_pages=args.max_source_pages,
        )
    else:
        log.error("unsupported source: %s", args.source)
        return 1
    log.info("  → %d unique companies from %s", len(listings), args.source)

    log.info("step 2/3: 求人ボックス existence check (AI 一致判定, 5s 間隔)")
    rows: list[dict] = []
    extractor = ClaudeExtractor()
    async with KyujinboxScraper(access_delay=args.kyujinbox_access_delay) as ks:
        for i, li in enumerate(listings, 1):
            try:
                exists, search_url, listing_count, matched = await ks.check_existence(
                    li.company_name, extractor=extractor
                )
            except Exception as e:
                log.warning("[%d/%d] %s: check failed: %s", i, len(listings), li.company_name, e)
                continue
            tag = "EXISTS" if exists else "MISSING"
            log.info("[%d/%d] %s %s (listings=%d, matched=%d)",
                     i, len(listings), tag, li.company_name, listing_count, len(matched))
            rows.append({
                "company_name": li.company_name,
                "job_title": li.job_title,
                "source": args.source,
                "source_url": li.job_url,
                "kyujinbox_search_url": search_url,
                "kyujinbox_exists": exists,
                "kyujinbox_listing_count": listing_count,
                "kyujinbox_matched_names": matched,
            })

    log.info("step 3/3: 出力")
    csv_path = out_dir / "unmatched_leads.csv"
    json_path = out_dir / "unmatched_leads.json"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "company_name", "job_title", "source", "source_url",
            "kyujinbox_search_url", "kyujinbox_exists",
            "kyujinbox_listing_count", "kyujinbox_matched_names",
        ])
        writer.writeheader()
        for r in rows:
            row = dict(r)
            row["kyujinbox_matched_names"] = " | ".join(row["kyujinbox_matched_names"])
            writer.writerow(row)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    # サマリ
    n_total = len(rows)
    n_missing = sum(1 for r in rows if not r["kyujinbox_exists"])
    n_exists = n_total - n_missing
    log.info("done: total=%d, kyujinbox_exists=%d, MISSING(リード候補)=%d",
             n_total, n_exists, n_missing)
    log.info("output: %s, %s", csv_path, json_path)
    return 0


def main() -> int:
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ANTHROPIC_API_KEY_SCRIPTS"):
        os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY_SCRIPTS"]
    args = parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
