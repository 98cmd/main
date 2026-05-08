from __future__ import annotations

import logging
from dataclasses import dataclass

import anthropic

from .extractor import CompanyDetail

log = logging.getLogger(__name__)

MODEL_ID = "claude-opus-4-7"


@dataclass
class SenderProfile:
    name: str
    company: str
    email: str
    service_name: str
    service_description: str


SYSTEM_TEMPLATE = """\
あなたは BtoB 営業のコピーライターです。求人媒体「求人ボックス」の代理店として、
人材紹介・人材派遣会社向けに、現在ご利用中の求人媒体からの切り替えを提案する
問い合わせフォーム送信用の営業文章を作成してください。

# 自社プロフィール
- 担当者名: {sender_name}
- 会社名: {sender_company}
- 連絡先メール: {sender_email}
- 提案サービス: {service_name}
- サービス概要: {service_description}

# 文章の要件
- 300〜500字、日本語、敬体（です・ます）。
- 件名 / 本文 の順で、空行で区切る。
- 件名は20〜35字、相手企業名ありき・売り込み臭さを抑える。
- 本文冒頭で相手の事業を一行リサーチ気味に触れる（industry_summary を活用）。
- 自社の主張は2〜3行に絞り、料金やクリック単価を断定しない。
- 末尾は「30分のオンライン情報交換」を控えめに打診。
- 強い CTA や絵文字、誇張表現（最安・No.1 など）は使用しない。
- 同一文面の使い回しに見えないよう、相手企業の文脈に沿わせて表現を毎回少しずつ変える。
"""


class OutreachGenerator:
    def __init__(self, sender: SenderProfile, client: anthropic.Anthropic | None = None):
        self.sender = sender
        self.client = client or anthropic.Anthropic()
        self._system_text = SYSTEM_TEMPLATE.format(
            sender_name=sender.name,
            sender_company=sender.company,
            sender_email=sender.email,
            service_name=sender.service_name,
            service_description=sender.service_description,
        )

    def generate(self, company: CompanyDetail) -> str:
        user_prompt = (
            f"宛先企業: {company.company_name}\n"
            f"自社サイト: {company.company_website or '(不明)'}\n"
            f"事業概要: {company.industry_summary or '(不明)'}\n"
            f"許可番号: {company.license_number or '(不明)'}\n"
            "上記企業向けに、件名と本文を作成してください。"
        )
        response = self.client.messages.create(
            model=MODEL_ID,
            max_tokens=1500,
            system=[
                {
                    "type": "text",
                    "text": self._system_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
        return next(b.text for b in response.content if b.type == "text").strip()
