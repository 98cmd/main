"""中断したジョブのログから途中結果を抽出して JSON/CSV 化する。

ログ形式:
  [N/M] EXISTS/MISSING 会社名 (listings=X, matched=Y)

会社名から source_url を引くため、マイナビをもう一度叩いて当該会社を含む
リストを取得し、merge する。
"""
from __future__ import annotations
import argparse
import csv
import json
import logging
import re
import unicodedata
from pathlib import Path

from kyujinbox_poc.mynavi import fetch_listings as fetch_mynavi

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("extract")

PATTERN = re.compile(
    r"\[(\d+)/\d+\]\s+(EXISTS|MISSING)\s+(.+?)\s+\(listings=(\d+),\s*matched=(\d+)\)"
)


def _norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", (s or "").strip()).split())


def parse_log(log_path: Path) -> list[dict]:
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    rows = []
    for m in PATTERN.finditer(text):
        idx, status, name, listings, matched = m.groups()
        rows.append({
            "idx": int(idx),
            "company_name": name.strip(),
            "kyujinbox_exists": status == "EXISTS",
            "kyujinbox_listing_count": int(listings),
            "kyujinbox_matched_count": int(matched),
        })
    return rows


def merge_with_mynavi(parsed: list[dict], mynavi_max: int = 200) -> list[dict]:
    """会社名で merge して source_url を埋める。"""
    log.info("マイナビから %d 社を再取得（merge 用）", mynavi_max)
    mynavi_listings = fetch_mynavi(max_companies=mynavi_max, access_delay=5.0, max_pages=10)
    by_name = {_norm(li.company_name): li for li in mynavi_listings}
    out = []
    for r in parsed:
        key = _norm(r["company_name"])
        li = by_name.get(key)
        out.append({
            "company_name": r["company_name"],
            "job_title": li.job_title if li else "",
            "source": "mynavi",
            "source_url": li.job_url if li else "",
            "kyujinbox_search_url": "",  # ログには無い
            "kyujinbox_exists": r["kyujinbox_exists"],
            "kyujinbox_listing_count": r["kyujinbox_listing_count"],
            "kyujinbox_matched_names": [r["company_name"]] * r["kyujinbox_matched_count"]
                if r["kyujinbox_matched_count"] > 0 else [],
        })
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--log", default="output/cross_filter_v2.log")
    p.add_argument("--out-json", default="output/unmatched_leads.json")
    p.add_argument("--out-csv", default="output/unmatched_leads.csv")
    p.add_argument("--no-merge", action="store_true", help="マイナビ再取得をスキップ")
    p.add_argument("--mynavi-max", type=int, default=200)
    args = p.parse_args()

    parsed = parse_log(Path(args.log))
    log.info("parsed %d rows from log", len(parsed))
    if not parsed:
        log.error("no rows")
        return 1

    rows = parsed if args.no_merge else merge_with_mynavi(parsed, args.mynavi_max)

    Path(args.out_json).write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fieldnames = list(rows[0].keys()) if rows else []
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            row = dict(r)
            if isinstance(row.get("kyujinbox_matched_names"), list):
                row["kyujinbox_matched_names"] = " | ".join(row["kyujinbox_matched_names"])
            w.writerow(row)

    n_total = len(rows)
    n_missing = sum(1 for r in rows if not r["kyujinbox_exists"])
    log.info("done: total=%d, MISSING=%d (%.0f%%)",
             n_total, n_missing, n_missing*100/max(1, n_total))
    log.info("output: %s, %s", args.out_json, args.out_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
