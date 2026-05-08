from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import unicodedata
from pathlib import Path

from dotenv import load_dotenv


def _normalize_company_name(name: str) -> str:
    """重複排除用の正規化。NFKC（全角→半角等）+ trim + 連続空白を 1 つに圧縮。"""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).strip()
    return " ".join(s.split())

from kyujinbox_poc.extractor import ClaudeExtractor, CompanyDetail
from kyujinbox_poc.generator import OutreachGenerator, SenderProfile
from kyujinbox_poc.mhlw import MHLWLookup, pick_primary
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
    p.add_argument("--mhlw", action="store_true", help="厚労省サイトで許可番号・住所・電話を補完")
    p.add_argument("--dry-run", action="store_true",
                   help="samples/ のサンプル HTML から listing 抽出のみ実行。実サイトに接続しない")
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
    mhlw_ctx = MHLWLookup(access_delay=3.0) if args.mhlw else None

    # --dry-run: サンプル HTML から listing 抽出のみ実行（実サイトには行かない）
    if args.dry_run:
        sample = Path(__file__).resolve().parent / "samples" / "kyujinbox_search.html"
        if not sample.exists():
            log.error("dry-run sample missing: %s", sample)
            return 1
        log.info("DRY RUN: using %s (no live fetch)", sample)
        listings = extractor.extract_listings(sample.read_text(encoding="utf-8"))
        log.info("dry-run extracted %d listings", len(listings))
        for i, l in enumerate(listings, 1):
            tag = "STAFF" if l.is_staffing_or_dispatch_company else "other"
            log.info("  [%d] %s [%s] %s -> %s", i, tag, l.company_name, l.job_title[:40], l.detail_url)
        return 0

    targets: list[CompanyDetail] = []

    if mhlw_ctx is not None:
        await mhlw_ctx.__aenter__()
    async with KyujinboxScraper(access_delay=args.access_delay) as scraper:
        seen_urls: set[str] = set()
        seen_companies: set[str] = set()  # 会社名ベースで重複排除（NFKC 正規化済みのキーを保持）
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
                listing_key = _normalize_company_name(listing.company_name)
                if listing_key and listing_key in seen_companies:
                    log.info("skip duplicate company (listing): %s", listing.company_name)
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
                        kyujinbox_company_url="",
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

                # detail 抽出後にも会社名で重複排除（listing と detail で会社名が変わるケース対応）
                detail_key = _normalize_company_name(detail.company_name)
                if detail_key and detail_key in seen_companies:
                    log.info("skip duplicate company (detail): %s", detail.company_name)
                    continue
                if detail_key:
                    seen_companies.add(detail_key)
                if listing_key and listing_key != detail_key:
                    seen_companies.add(listing_key)

                # 厚労省サイト補完（オプション）
                if mhlw_ctx is not None and detail.company_name:
                    try:
                        mhlw_data = await mhlw_ctx.lookup(detail.company_name)
                        # 紹介を優先、無ければ派遣
                        primary = (
                            pick_primary(mhlw_data["shoukai"], detail.company_name)
                            or pick_primary(mhlw_data["haken"], detail.company_name)
                        )
                        total = len(mhlw_data["shoukai"]) + len(mhlw_data["haken"])
                        detail.mhlw_office_count = total
                        if mhlw_data["shoukai"] and mhlw_data["haken"]:
                            detail.mhlw_kind = "both"
                        elif mhlw_data["shoukai"]:
                            detail.mhlw_kind = "shoukai"
                        elif mhlw_data["haken"]:
                            detail.mhlw_kind = "haken"
                        if primary:
                            if not detail.license_number:
                                detail.license_number = primary.license_number
                            if not detail.address:
                                detail.address = primary.address
                            if not detail.phone:
                                detail.phone = primary.phone
                    except Exception as exc:
                        log.warning("MHLW lookup failed for %s: %s", detail.company_name, exc)

                if generator is not None:
                    try:
                        detail.outreach_message = generator.generate(detail)
                    except Exception as exc:
                        log.warning("generation failed for %s: %s", detail.company_name, exc)

                targets.append(detail)
                log.info("[%s/%s] %s", len(targets), args.max_listings, detail.company_name)

    if mhlw_ctx is not None:
        await mhlw_ctx.__aexit__(None, None, None)

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
                "kyujinbox_company_url",
                "address",
                "phone",
                "mhlw_kind",
                "mhlw_office_count",
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
    # CLAUDE.md ルール準拠: ANTHROPIC_API_KEY を恒久 env に置かず、ANTHROPIC_API_KEY_SCRIPTS
    # からプロセス起動時のみ流し込む。Claude Code Max サブスクと別の従量課金キーを分離する。
    if not os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ANTHROPIC_API_KEY_SCRIPTS"):
        os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY_SCRIPTS"]
    args = parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
