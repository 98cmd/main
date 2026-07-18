"""cross_filter の MISSING リード（求人ボックス未出稿）に対して営業文章を生成する。

入力: output/unmatched_leads.json （cross_filter.py の出力）
出力: output/lead_outreach_messages.csv / .json

cross_filter は会社名のみを抽出するので、industry_summary は Wantedly の
求人タイトル（phase1 由来）または「Wantedly 掲載企業」（phase2 由来）で代用。
公式サイト・許可番号・住所等は不明扱い（必要なら厚労省連携や Google CSE 検索で
補完するパスを後段で追加）。

使用例:
    .venv/Scripts/python.exe generate_for_leads.py
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from kyujinbox_poc.extractor import CompanyDetail
from kyujinbox_poc.generator import OutreachGenerator, SenderProfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("generate_for_leads")


# Wantedly 自社や明らかな誤陽性を除外するブラックリスト
EXCLUDE_COMPANY_NAMES = {
    "wantedly, inc.",
    "wantedly,inc.",
    "wantedlyinc",
}


def _norm(s: str) -> str:
    import unicodedata
    return " ".join(unicodedata.normalize("NFKC", (s or "").strip()).split()).lower()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MISSING リードに営業文章を生成")
    p.add_argument("--input", default="output/unmatched_leads.json")
    p.add_argument("--output-csv", default="output/lead_outreach_messages.csv")
    p.add_argument("--output-json", default="output/lead_outreach_messages.json")
    p.add_argument("--throttle", type=float, default=0.5,
                   help="API 呼び出し間のスリープ秒（rate limit 配慮）")
    p.add_argument("--limit", type=int, default=0,
                   help="先頭 N 件のみ生成（0 = 全件）")
    return p.parse_args()


def build_sender_from_env() -> SenderProfile:
    return SenderProfile(
        name=os.environ.get("SENDER_NAME", "高屋 裕司"),
        company=os.environ.get("SENDER_COMPANY", "株式会社UPDRAFT"),
        email=os.environ.get("SENDER_EMAIL", "takaya@updraft.example"),
        service_name=os.environ.get(
            "SERVICE_NAME",
            "求人ボックス代理店プログラム",
        ),
        service_description=os.environ.get(
            "SERVICE_DESCRIPTION",
            "求人ボックス（カカクコム運営）の正規代理店として、人材紹介・人材派遣会社向けに、"
            "現在ご利用中の求人媒体より好条件での切り替えをご提案しています。"
            "クリック単価の優遇や運用支援が強みです。",
        ),
    )


def main() -> int:
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ANTHROPIC_API_KEY_SCRIPTS"):
        os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY_SCRIPTS"]
    args = parse_args()

    inp = Path(args.input)
    if not inp.exists():
        log.error("input not found: %s", inp)
        return 1

    data = json.loads(inp.read_text(encoding="utf-8"))
    miss = [r for r in data if not r.get("kyujinbox_exists")]
    excluded: list[str] = []
    filtered: list[dict] = []
    for r in miss:
        if _norm(r.get("company_name", "")) in EXCLUDE_COMPANY_NAMES:
            excluded.append(r.get("company_name", ""))
            continue
        filtered.append(r)
    if excluded:
        log.info("excluded %d false-positives: %s", len(excluded), excluded)
    if args.limit > 0:
        filtered = filtered[: args.limit]
    log.info("targets: %d MISSING leads", len(filtered))

    sender = build_sender_from_env()
    log.info("sender: %s / %s / %s", sender.name, sender.company, sender.email)

    gen = OutreachGenerator(sender)

    rows: list[dict] = []
    for i, r in enumerate(filtered, 1):
        co_name = r["company_name"]
        wantedly_job = r.get("job_title") or ""
        industry_summary = wantedly_job or "Wantedly に求人を掲載中の企業（業種詳細は未取得）"
        cd = CompanyDetail(
            company_name=co_name,
            company_website="",
            contact_form_url="",
            industry_summary=industry_summary,
            license_number="",
            is_staffing_or_dispatch_company=False,
            source_url=r.get("source_url", ""),
        )
        log.info("[%d/%d] %s", i, len(filtered), co_name)
        try:
            msg = gen.generate(cd)
        except Exception as e:
            log.warning("generate failed for %s: %s", co_name, e)
            msg = f"(生成失敗: {e})"
        rows.append({
            "company_name": co_name,
            "wantedly_url": r.get("source_url", ""),
            "wantedly_job_title": wantedly_job,
            "kyujinbox_search_url": r.get("kyujinbox_search_url", ""),
            "kyujinbox_listing_count": r.get("kyujinbox_listing_count", 0),
            "outreach_message": msg,
        })
        if args.throttle > 0:
            time.sleep(args.throttle)

    out_csv = Path(args.output_csv)
    out_json = Path(args.output_json)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "company_name",
        "wantedly_url",
        "wantedly_job_title",
        "kyujinbox_search_url",
        "kyujinbox_listing_count",
        "outreach_message",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    out_json.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("done: wrote %s + %s (rows=%d)", out_csv, out_json, len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
