from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any
from urllib.parse import urlparse, urlunparse

import anthropic

KYUJINBOX_HOST = "xn--pckua2a7gp15o89zb.com"


def _normalize_kyujinbox_url(u: str) -> str:
    """LLM が detail_url を "kyujinbox.com" 等に幻覚で書き換えた場合、punycode ホストに戻す。"""
    if not u:
        return u
    try:
        parsed = urlparse(u)
        if parsed.netloc and parsed.netloc != KYUJINBOX_HOST:
            # kyujinbox 系の幻覚ホストは強制的に punycode に置換
            if "kyujinbox" in parsed.netloc.lower() or parsed.netloc.endswith(".com"):
                return urlunparse(parsed._replace(netloc=KYUJINBOX_HOST))
        return u
    except Exception:
        return u

log = logging.getLogger(__name__)

import os
MODEL_ID = os.getenv("MODEL_ID", "claude-sonnet-4-6")
EXTRACT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "listings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "company_name": {"type": "string"},
                    "job_title": {"type": "string"},
                    "location": {"type": "string"},
                    "detail_url": {"type": "string"},
                    "is_staffing_or_dispatch_company": {"type": "boolean"},
                },
                "required": [
                    "company_name",
                    "job_title",
                    "location",
                    "detail_url",
                    "is_staffing_or_dispatch_company",
                ],
            },
        }
    },
    "required": ["listings"],
}

DETAIL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "company_name": {"type": "string"},
        "company_website": {"type": "string"},
        "contact_form_url": {"type": "string"},
        "industry_summary": {"type": "string"},
        "license_number": {"type": "string"},
        "kyujinbox_company_url": {"type": "string"},
        "is_staffing_or_dispatch_company": {"type": "boolean"},
    },
    "required": [
        "company_name",
        "company_website",
        "contact_form_url",
        "industry_summary",
        "license_number",
        "kyujinbox_company_url",
        "is_staffing_or_dispatch_company",
    ],
}


@dataclass
class Listing:
    company_name: str
    job_title: str
    location: str
    detail_url: str
    is_staffing_or_dispatch_company: bool


@dataclass
class CompanyDetail:
    company_name: str
    company_website: str
    contact_form_url: str
    industry_summary: str
    license_number: str
    is_staffing_or_dispatch_company: bool
    source_url: str = ""  # 求人ボックスの求人詳細ページ URL
    kyujinbox_company_url: str = ""  # 求人ボックスの会社専用ページ（あれば）
    listing: Listing | None = None
    outreach_message: str = ""
    # 厚労省サイトからの補完情報
    address: str = ""
    phone: str = ""
    mhlw_kind: str = ""  # "shoukai" / "haken" / 両方なら "both"
    mhlw_office_count: int = 0  # 検索ヒット事業所数

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("listing", None)
        return row


SYSTEM_PROMPT_LISTING = """\
あなたは求人ボックス（kyujinbox / カカクコム運営）の検索結果ページを解析し、
人材紹介・人材派遣会社による掲載求人を抽出するアシスタントです。

抽出ルール:
- 求人カードを1つずつ抽出する。
- detail_url は絶対URL（https://...）に正規化する。
- 「○○エージェント」「人材紹介」「人材派遣」「派遣社員募集」など、人材紹介・人材派遣会社と
  推定できる求人は is_staffing_or_dispatch_company=true とする。それ以外は false。
- ページが空、または対象がいない場合は listings: [] を返す。
- 推測情報を埋めない。HTMLに無い項目は空文字列にする。
"""

SYSTEM_PROMPT_DETAIL = """\
あなたは求人ボックスの求人詳細ページから、掲載企業の連絡先情報を抽出するアシスタントです。

抽出ルール:
- company_website は掲載企業の自社サイトURL（求人ボックス内のURLは不可）。
- contact_form_url は問い合わせフォームのURL。トップページしか分からない場合は空文字。
- license_number は「(派) ○○-○○」「有料職業紹介許可番号 ○○」等の許可番号。無ければ空文字。
- industry_summary は1〜2行で当該企業のビジネスを要約（人材紹介専業／製造特化派遣／など）。
- kyujinbox_company_url は **求人ボックス内の会社専用ページ** の URL（例: 「この企業の他の求人を見る」リンクの先、`/co/<id>` や `/cm/<id>` のようなパス）。求人詳細ページそのもの（/jb/<hash>）は不可。見つからない場合は空文字列。punycode ホスト `xn--pckua2a7gp15o89zb.com` を使うこと。
- 不明な項目は空文字列にする。憶測で補完しない。
"""


class ClaudeExtractor:
    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()

    def extract_listings(self, html: str) -> list[Listing]:
        response = self.client.messages.create(
            model=MODEL_ID,
            max_tokens=16000,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT_LISTING,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            output_config={
                "format": {"type": "json_schema", "schema": EXTRACT_SCHEMA}
            },
            messages=[{"role": "user", "content": html}],
        )
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
        items = []
        for raw in data["listings"]:
            raw["detail_url"] = _normalize_kyujinbox_url(raw.get("detail_url", ""))
            items.append(Listing(**raw))
        return items

    def extract_detail(self, html: str, source_url: str = "") -> CompanyDetail:
        response = self.client.messages.create(
            model=MODEL_ID,
            max_tokens=8000,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT_DETAIL,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            output_config={
                "format": {"type": "json_schema", "schema": DETAIL_SCHEMA}
            },
            messages=[{"role": "user", "content": html}],
        )
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
        # kyujinbox_company_url も幻覚対策で正規化
        if "kyujinbox_company_url" in data:
            data["kyujinbox_company_url"] = _normalize_kyujinbox_url(data["kyujinbox_company_url"])
        return CompanyDetail(source_url=source_url, **data)
