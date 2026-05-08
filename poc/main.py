from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from kyujinbox_poc.extractor import ClaudeExtractor, CompanyDetail
from kyujinbox_poc.generator import OutreachGenerator, SenderProfile
from kyujinbox_poc.scraper import KyujinboxScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("poc")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="求人ボックス PoC: 人材紹介・派遣会社の抽出 + 営業文章生成")
    p.add_argument("--query", default=os.getenv("KYUJINBOX_QUERY", "人材紹介 製造"))
    p.add_argument("--max-listings", type=int, default=int(os.getenv("MAX_LISTINGS", "10")))
    p.add_argument("--access-delay", type=float, default=float(os.getenv("ACCESS_DELAY_SECONDS", "5")))
    p.add_argument("--max-pages", type=int, default=2, help="検索結果ページ数の上限")
    p.add_argument("--output-dir", default="output")
    p.add_argument("--no-detail", action="store_true", help="詳細ページに行かず一覧情報のみで生成")
    p.add_argument("--no-generate", action="store_true", help="文章生成をスキップ（抽出のみ）")
    return p.parse_args()


def build_sender_profile() -> SenderProfile:
    return SenderProfile(
        name=os.getenv("SENDER_NAME", "高屋 裕司"),
        company=os.getenv("SENDER_COMPANY", "株式会社UPDRAFT"),
        email=os.getenv("SENDER_EMAIL", "info@example.com"),
        service_name=os.getenv("SERVICE_NAME", "求人ボックス代理店プログラム"),
        service_description=os.getenv(
            "SERVICE_DESCRIPTION",
            "求人ボックスの正規代理店として、現在ご利用中の求人媒体より好条件での切り替えをご提案。",
        ),
    )


async def run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    extractor = ClaudeExtractor()
    sender = build_sender_profile()
    generator = None if args.no_generate else OutreachGenerator(sender)

    targets: list[CompanyDetail] = []

    async with KyujinboxScraper(access_delay=args.access_delay) as scraper:
        seen_urls: set[str] = set()
        for page_no in range(1, args.max_pages + 1):
            if len(targets) >= args.max_listings:
                break
            page = await scraper.fetch_search(args.query, page_no)
            listings = extractor.extract_listings(page.cleaned_html)
            log.info("page=%s listings=%s", page_no, len(listings))

            for listing in listings:
                if len(targets) >= args.max_listings:
                    break
                if not listing.is_staffing_or_dispatch_company:
                    continue
                if listing.detail_url in seen_urls:
                    continue
                seen_urls.add(listing.detail_url)

                if args.no_detail:
                    detail = CompanyDetail(
                        company_name=listing.company_name,
                        company_website="",
                        contact_form_url="",
                        industry_summary=listing.job_title,
                        license_number="",
                        is_staffing_or_dispatch_company=True,
                        source_url=listing.detail_url,
                        listing=listing,
                    )
                else:
                    try:
                        detail_page = await scraper.fetch_detail(listing.detail_url)
                        detail = extractor.extract_detail(detail_page.cleaned_html, listing.detail_url)
                        detail.listing = listing
                    except Exception as exc:
                        log.warning("detail fetch failed: %s — %s", listing.detail_url, exc)
                        continue

                if generator is not None:
                    try:
                        detail.outreach_message = generator.generate(detail)
                    except Exception as exc:
                        log.warning("generation failed for %s: %s", detail.company_name, exc)

                targets.append(detail)
                log.info("[%s/%s] %s", len(targets), args.max_listings, detail.company_name)

    csv_path = output_dir / "results.csv"
    json_path = output_dir / "results.json"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "company_name",
                "company_website",
                "contact_form_url",
                "industry_summary",
                "license_number",
                "is_staffing_or_dispatch_company",
                "source_url",
                "outreach_message",
            ],
        )
        writer.writeheader()
        for t in targets:
            writer.writerow(t.to_row())

    with json_path.open("w", encoding="utf-8") as f:
        json.dump([t.to_row() for t in targets], f, ensure_ascii=False, indent=2)

    log.info("done: %s targets → %s, %s", len(targets), csv_path, json_path)
    return 0


def main() -> int:
    load_dotenv()
    args = parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
