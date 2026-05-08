# 求人ボックス PoC：人材紹介・派遣会社の抽出 + 営業文章生成

5/7ミーティングで決まった「求人ボックスから人材紹介・派遣会社を抽出して直接アプローチ」案の **第1段階（抽出 + AI文章生成）** をスクリプト化したもの。フォーム送信は意図的に**未実装**。

## ⚠️ 利用規約・法務に関する注意

- 求人ボックスの利用規約は自動取得を制限している可能性があります。本PoCは**自社調査・小規模検証のみ**を想定し、`ACCESS_DELAY_SECONDS=5` と `MAX_LISTINGS=10` を既定にしています。**商用大量実行はそのままでは行わないでください。**
- 取得対象は**ログイン不要の公開ページのみ**。ログイン必須ページは対象外です。
- 取得した情報は社内利用に限定し、第三者への配布・再公開は行わないこと。
- 本物の問い合わせフォームへの自動送信は **このPoCには含まれません**。次フェーズ実装時に法務確認を行ってください。

## 構成

```
poc/
├── main.py                          # CLIエントリーポイント
├── requirements.txt
├── .env.example
├── kyujinbox_poc/
│   ├── scraper.py                   # Playwrightで求人ボックスにアクセス
│   ├── extractor.py                 # HTML → 構造化データ（Claude）
│   └── generator.py                 # 営業文章生成（Claude + プロンプトキャッシュ）
└── output/                          # results.csv / results.json が出力される
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

## 実行

```bash
# 既定: クエリ「人材紹介 製造」、最大10社、5秒間隔
python main.py

# クエリと件数を指定
python main.py --query "人材派遣 製造" --max-listings 5

# 一覧情報のみで文章生成（詳細ページにアクセスしない・速い）
python main.py --no-detail

# 抽出のみで文章生成をスキップ
python main.py --no-generate
```

## 出力

- `output/results.csv` — Excel等で開く用
- `output/results.json` — プログラムから扱う用

各行に `company_name`, `company_website`, `contact_form_url`, `industry_summary`, `license_number`, `source_url`, `outreach_message` が入る。

## 設計メモ

- **HTMLパースはAI任せ**。CSSセレクタを書き込んでいないので、求人ボックス側のマークアップ変更で壊れにくい。代わりに1社あたり数円の API コストが発生。
- **モデル**: Claude Opus 4.7 (`claude-opus-4-7`)。抽出と文章生成で共通。
- **プロンプトキャッシュ**: システムプロンプトに `cache_control: ephemeral` を付与済み。複数件を続けて処理する際にコストが下がる。
- **アクセス間隔**: 既定5秒。`--access-delay` で調整可能。負荷をかけない範囲で運用すること。

## 既知の制約

- 求人ボックスは中身がJSレンダリングなので Playwright 必須。`requests` だけでは中身が取れない。
- `detail_url` が相対パスの場合、AIが絶対URLに正規化するよう指示しているが取りこぼしの可能性あり。
- `is_staffing_or_dispatch_company` の判定はAI推定。誤判定はあり得る。
- フォーム送信側のシステムは別途実装が必要（`feasibility-report.md` 第1フェーズ参照）。

## 次のステップ

1. 10社程度で実行し、`industry_summary` の精度と `outreach_message` の質を人間レビュー
2. `contact_form_url` の取得率を計測（取れない場合のフォールバック検討）
3. 厚労省「人材サービス総合サイト」を補助データソースとして突合
4. （別検討案件）フォーム自動送信エンジンの法務レビュー → 実装
