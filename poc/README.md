# 求人ボックス PoC：人材紹介・派遣会社の抽出 + 営業文章生成

5/7ミーティングで決まった「求人ボックスから人材紹介・派遣会社を抽出して直接アプローチ」案の **第1段階（抽出 + AI文章生成 + 厚労省補完）** をスクリプト化したもの。フォーム送信は意図的に**未実装**。

## 実証結果（2026-05-08, 5社サンプル）

| 指標 | 値 |
|------|------|
| 人材紹介・派遣判定精度 | 5/5（100%） |
| `license_number` 取得率 | **80%**（厚労省補完あり） |
| `address` 取得率 | **80%**（厚労省補完） |
| `phone` 取得率 | **80%**（厚労省補完） |
| `company_website` 取得率 | 20%（求人ボックス詳細から） |
| `outreach_message` 品質 | 各社事業特性に沿った個別文面、AIっぽさ低 |
| 1社あたりコスト | **約 12円**（Sonnet 4.6 / Opus 4.7 だと 60円） |
| 1社あたり所要時間 | 約 90 秒（MHLW 補完含む。なしだと 30 秒） |

## ⚠️ 利用規約・法務に関する注意

- 求人ボックスの利用規約は自動取得を制限している可能性があります。本PoCは**自社調査・小規模検証のみ**を想定し、`ACCESS_DELAY_SECONDS=5` と `MAX_LISTINGS=10` を既定にしています。**商用大量実行はそのままでは行わないでください。**
- 取得対象は**ログイン不要の公開ページのみ**。ログイン必須ページは対象外です。
- 取得した情報は社内利用に限定し、第三者への配布・再公開は行わないこと。
- 本物の問い合わせフォームへの自動送信は **このPoCには含まれません**。次フェーズ実装時に法務確認を行ってください。
- 厚労省「人材サービス総合サイト」は公開・公的サイトで利用規約上の制約が緩いが、念のためアクセス間隔 3 秒以上を空けています。

## 構成

```
poc/
├── main.py                          # CLIエントリーポイント
├── requirements.txt
├── .env.example
├── kyujinbox_poc/
│   ├── scraper.py                   # Playwrightで求人ボックスにアクセス
│   ├── extractor.py                 # HTML → 構造化データ（Claude）+ URL正規化
│   ├── generator.py                 # 営業文章生成（Claude + プロンプトキャッシュ）
│   └── mhlw.py                      # 厚労省サイトで許可番号・住所・電話を補完
├── samples/                         # オフラインテスト用サンプル HTML
│   ├── kyujinbox_search.html
│   ├── mhlw_search_shoukai.html
│   └── mhlw_search_haken.html
├── tests/                           # 単体テスト（API/サイト不要）
│   ├── test_extractor_normalize.py
│   └── test_mhlw_parse.py
├── debug_*.py                       # 開発用デバッグスクリプト（network 観察など）
└── output/                          # results.csv / results.json が出力される（git ignore）
```

## セットアップ

```bash
cd poc
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# .env を編集して ANTHROPIC_API_KEY と SENDER_* を設定
```

`ANTHROPIC_API_KEY` を恒久 env に置きたくない環境（Claude Max サブスク認証と分けたい等）では、`ANTHROPIC_API_KEY_SCRIPTS` という別名の env を `.env` か OS の User scope に置けば、`main.py` 起動時にプロセス内のみフォールバックされます。

## 実行

```bash
# 既定: クエリ「人材紹介 製造」、最大10社、5秒間隔
python main.py

# クエリと件数を指定
python main.py --query "人材派遣 製造" --max-listings 5

# 厚労省サイトで許可番号・住所・電話を補完
python main.py --max-listings 5 --mhlw

# サンプル HTML から listing 抽出のみ（実サイト不要、開発用）
python main.py --dry-run

# 一覧情報のみで文章生成（詳細ページにアクセスしない・速い）
python main.py --no-detail

# 抽出のみで文章生成をスキップ
python main.py --no-generate
```

### モデル切替

`extractor.py` / `generator.py` は環境変数 `MODEL_ID` でモデルを上書きできます。既定は **`claude-sonnet-4-6`**（コスト・速度バランスが良く、抽出・文章生成とも実用品質）。

```bash
MODEL_ID=claude-opus-4-7 python main.py --max-listings 5  # Opus に切替（5倍コスト）
```

## テスト

サンプル HTML を使ったオフライン単体テストが `tests/` にあります。実 API/サイト不要。

```bash
python -m unittest discover -s tests -v
```

## 出力

- `output/results.csv` — Excel等で開く用
- `output/results.json` — プログラムから扱う用

各行に `company_name`, `company_website`, `contact_form_url`, `industry_summary`, `license_number`, `address`, `phone`, `mhlw_kind`, `mhlw_office_count`, `source_url`, `outreach_message` が入る。

## 設計メモ

- **HTMLパースはAI任せ**。CSSセレクタを書き込んでいないので、求人ボックス側のマークアップ変更で壊れにくい。代わりに1社あたり数円の API コストが発生。
- **モデル**: 既定 Claude Sonnet 4.6 (`claude-sonnet-4-6`)。抽出と文章生成で共通。Opus 4.7 にも切替可能だが本タスクには過剰。
- **プロンプトキャッシュ**: システムプロンプトに `cache_control: ephemeral` を付与済み。複数件を続けて処理する際にコストが下がる。
- **アクセス間隔**: 求人ボックスは既定 5 秒、厚労省は 3 秒。負荷をかけない範囲で運用すること。
- **URL 正規化**: LLM が `detail_url` を実在しないドメイン（`kyujinbox.com` 等）に幻覚で書き換えることがあるため、`extractor._normalize_kyujinbox_url()` で punycode ホスト (`xn--pckua2a7gp15o89zb.com`) に強制置換。
- **重複排除**: 同じ会社の別求人を別件としてカウントしないよう、`seen_companies` セットで会社名ベースで除外。
- **厚労省連携**: `--mhlw` 時、各企業について「職業紹介事業」「労働者派遣事業」の両方で会社名検索 → 許可番号・住所・電話を補完。3 段階画面遷移（GICB101010 → GICB102030 → GICB102060）を Playwright で再現。

## 既知の制約

- 求人ボックスは中身がJSレンダリングなので Playwright 必須。`requests` だけでは中身が取れない。
- `is_staffing_or_dispatch_company` の判定はAI推定。誤判定はあり得る。
- 厚労省検索は会社名の**部分一致**だが、登録名と入力名の表記揺れ（例:「ビータス」が登録上は別表記）でヒット 0 件になることがある。
- フォーム送信側のシステムは別途実装が必要（`feasibility-report.md` 第1フェーズ参照）。

## 次のステップ

1. 10〜100社規模で実行し、`industry_summary` / `outreach_message` の品質を人間レビュー
2. `company_website` 取得率を上げるため、Google 検索や厚労省 → 自社 URL 補完パイプライン追加
3. 厚労省検索の表記揺れフォールバック（カタカナ/漢字/英字 と 全角/半角 のバリエーション）
4. （別検討）フォーム自動送信エンジンの法務レビュー → 実装
