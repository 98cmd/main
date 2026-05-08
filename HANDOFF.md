# 引き継ぎ書（HANDOFF）

別ターミナルでも作業を続けられるようにするためのまとめ。
新しい Claude / 開発者はこのファイルを読めば現状と次の選択肢を把握できる。

最終更新: 2026-05-09（cross_filter / マイナビ・Wantedly source / Wantedly リード率 35% を実証）

---

## 1. プロジェクトの目的（30秒サマリー）

- **依頼者**: 株式会社UPDRAFT 高屋裕司氏
- **ゴール**: 求人ボックス（カカクコム運営）に掲載中の **人材紹介・人材派遣会社** に直接アプローチして、求人ボックス代理店としての売上を伸ばす
- **アプローチ**: 求人媒体から自動でターゲット情報を抽出 → AIで個別文章生成 → 問い合わせフォームへ自動送信（最終形）
- **背景**: 2026/05/07 のPRES社 福井氏との打ち合わせ（議事録は `feasibility-report.md` 参照）。来週中に技術検証結果を回答する約束あり。

---

## 2. リポジトリ情報

| 項目 | 値 |
|------|-----|
| リポジトリ | `98cmd/main` |
| 作業ブランチ | `claude/review-system-requirements-FfPKg` |
| ベースブランチ | `main` |
| ドラフトPR | #2 — https://github.com/98cmd/main/pull/2 |
| プライマリ作業ディレクトリ | `/home/user/main` |

⚠️ **このブランチ以外にpushしないこと**。SessionStart hook で固定されている。

---

## 3. 現状のリポジトリ構成

```
.
├── HANDOFF.md                       # このファイル
├── feasibility-report.md            # 福井氏向けの実現可能性レポート（148行）
└── poc/                             # 求人ボックス PoC（抽出 + 文章生成）
    ├── main.py                      # CLI エントリ
    ├── requirements.txt
    ├── .env.example
    ├── README.md                    # 利用規約注意・使い方
    ├── kyujinbox_poc/
    │   ├── scraper.py               # Playwright で求人ボックスにアクセス
    │   ├── extractor.py             # HTML → 構造化JSON（Claude）
    │   └── generator.py             # 営業文章生成（Claude + プロンプトキャッシュ）
    └── output/                      # 実行結果が出る（.gitignore 済み）
```

### 採用技術
- **Python** 3.10+
- **Playwright** (Chromium) — 求人ボックスは JS レンダリングなので必須
- **Anthropic Python SDK** — 既定 `claude-sonnet-4-6` で抽出と文章生成（環境変数 `MODEL_ID` で上書き可）
- **Prompt Caching** — システムプロンプトに `cache_control: ephemeral` を付与
- **Structured Outputs** — `output_config.format` (json_schema) で抽出結果を型付け
- **BeautifulSoup4** — 厚労省結果ページのテーブルパース

---

## 4. 完了済みのタスク

- [x] 5/7 ミーティング議事録の要約
- [x] **実現可能性レポート** 作成（`feasibility-report.md`）
  - 求人ボックス・Indeed・厚労省「人材サービス総合サイト」の3ソース評価
  - 概算コスト（初期115万円／ランニング月2〜3万円）
  - 法務リスク・ロードマップ
- [x] **PoC コード一式**（`poc/`）
  - 求人ボックスへの実サイト接続
  - 人材紹介・派遣会社の判定（AI推定）
  - 個別文章自動生成
  - CSV/JSON 出力
- [x] PR #2 をドラフトで作成
- [x] 利用規約への配慮（5秒間隔・10件キャップ・公開ページのみ）
- [x] **5/8 実測検証**（5社サンプル）
  - Sonnet 4.6 採用で精度同等・コスト 1/5 (≈12円/社)
  - 検索 URL の修正（パスベース `/<keyword>の仕事`）
  - LLM の URL 幻覚（`kyujinbox.com` への書き換え）対策（強制 punycode 化）
  - 会社名ベースの重複排除（同一企業の別求人を排除）
  - **厚労省連携実装**: 5社中 4社で許可番号・住所・電話を 100% 補完（80% カバレッジ）
- [x] **オフラインテスト追加**（`tests/`）: サンプル HTML で API/サイト不要の単体テスト（9 ケース通過、最新は 28 ケース）
- [x] **`--dry-run` モード**: サンプル HTML だけで listing 抽出を実行可能
- [x] **5/9 拡張**: 別媒体→求人ボックス未出稿フィルタ（`cross_filter.py`）
  - `kyujinbox_poc/mynavi.py`: マイナビ転職スクレイパ（urllib + BS4）
  - `kyujinbox_poc/wantedly.py`: Wantedly /projects から `__NEXT_DATA__` (Apollo state) 経由で会社名抽出
  - `scraper.check_existence()`: 会社名で求人ボックス検索 → AI listing 抽出 → NFKC 一致判定で過剰陽性を回避
  - `_strip_html` を 80K に縮小し Sonnet 抽出のコスト・速度改善
  - `build_html_leads.py`: cross_filter 結果の HTML viewer
  - `extract_partial.py`: 中断ジョブのログから途中結果を JSON 化
- [x] **5/9 提携媒体調査**: 求人ボックスの `/api/source-site-name-list` 全 94 媒体取得
  - 提携先は中小規模媒体・ATS 系（engage / ジョブカン / HRMOS / HERP / Talentio 等）
  - 主要転職媒体（doda / マイナビ / リクナビ / en / ビズリーチ / Wantedly / type / Forkwell / LinkedIn / Indeed）は **0 件提携**
  - マイナビ重複が高い理由 = 同社の ATS 経由集約のため、と判明
- [x] **5/9 リード抽出実測**:
  - マイナビ 30 社: MISSING 2 件（**リード率 7%**）
  - Wantedly 17 社: MISSING 6 件（**リード率 35%**）
  - スタートアップ系媒体ほど ATS 経由集約が少なく、求人ボックス未出稿の割合が高い

---

## 5. やっていない / 意図的に外したこと

- ❌ **問い合わせフォームへの自動送信** — 法務確認が必要なため次フェーズに切り出し
- ❌ **Indeed 対応** — Bot 対策厳しい・規約上のリスクで後回し
- ❌ **doda 対応** — Cloudflare/DataDome 系の保護で urllib・playwright・WebFetch 全て弾かれる。突破は別経路調査が必要（playwright firefox / 専用 proxy 等）
- ❌ **管理画面（送信履歴・進捗ダッシュボード）** — 第1フェーズ後半
- ✅ **厚労省サイト連携** — 5/8 で実装済（PR #2 反映済）
- ✅ **PoC 実行** — 5/8 〜 5/9 で実測済

PR #2 の Cloudflare Workers ビルド失敗は **このリポジトリと無関係** な環境的な失敗。スキップでOK（ユーザー確認済み）。

---

## 6. 次の選択肢（5/9 時点）

新しいセッションで作業を再開するなら、まず依頼者にどれを進めるか確認すること。

| # | やること | 概要 | 所要 |
|---|---------|------|------|
| A | **Wantedly 100 件**まで母集団拡大 | `--source wantedly --max-companies 100`（occupation_id カテゴリ巡回拡張）。リード率 35% で約 35 件のリード候補を期待 | 約 100 分 / ~$15 |
| B | **マイナビ + Wantedly 合算** | 多媒体マージで 100 件規模 | 同上 |
| C | **doda Cloudflare 突破調査** | playwright firefox / browser-use CLI / 専用 proxy 等で別経路試行 | 不確実、調査 1 時間 |
| D | **リクナビ NEXT / en 転職 / Forkwell 追加** | 媒体ポートフォリオ拡大、Wantedly 同様の URL 構造調査が必要 | 各 30〜60 分実装 |
| E | **既存リード 8 件で営業文章生成** | `cross_filter` の MISSING リストを generator にかけて文章付与 | 5 分 / ~$0.5 |
| F | **フォーム送信エンジンの設計書** | 第2フェーズ。Computer Use / 直接POST の比較設計、法務 RFC ドラフト | 約 30 分 |
| G | **PR #2 マージ判断・最終レポート** | レビュー反映、依頼者向けクライアントレポート整理 | 30〜60 分 |

おすすめは **A → E**（最高リード率を厚く取って即営業可能化）。

---

## 7. 環境セットアップ（新ターミナルで再開する場合）

```bash
# 既存 clone がなければ
git clone https://github.com/98cmd/main.git
cd main
git checkout claude/review-system-requirements-FfPKg

# 既存 clone があれば
git fetch origin && git checkout claude/review-system-requirements-FfPKg && git pull

# PoC セットアップ
cd poc
python -m venv .venv
# Windows: .venv\Scripts\activate / Mac/Linux: source .venv/bin/activate
.venv/Scripts/pip.exe install -r requirements.txt
.venv/Scripts/python.exe -m playwright install chromium

# API キー（CLAUDE.md ルール準拠）
# 永続的に持たず、一時的にプロセス env で渡す
export ANTHROPIC_API_KEY=sk-ant-...
# または .env (protect-files.sh hook でブロックされる場合は ANTHROPIC_API_KEY_SCRIPTS 別名)

# 既存 PoC を実行
.venv/Scripts/python.exe main.py --query "人材紹介 製造" --max-listings 5 --mhlw

# 別媒体→求人ボックス未出稿リード抽出
.venv/Scripts/python.exe cross_filter.py --source mynavi --max-companies 30
.venv/Scripts/python.exe cross_filter.py --source wantedly --max-companies 30

# テスト
.venv/Scripts/python.exe -m unittest discover -s tests

# 結果 HTML 化
.venv/Scripts/python.exe build_html.py        # results 用
.venv/Scripts/python.exe build_html_leads.py  # cross_filter 用
```

---

## 8. 重要な制約・注意

- **モデルID**: 既定は `claude-sonnet-4-6`（実測でコスト・精度のバランス最良）。`MODEL_ID` env で `claude-opus-4-7` に切替可（5倍コスト、用途による）。日付サフィックスは付けない。
- **求人ボックスへの自動取得は規約上グレー**。本PoCは小規模検証のみを想定し、大量実行はしない。
- **問い合わせフォーム送信の実装は意図的に未着手**。次フェーズで法務確認後に判断。
- **PRはドラフトのまま**（依頼者がレビューしたあとマージ判断）。
- **Cloudflare Workers ビルド失敗は無視**（このリポにWorkerコードなし）。
- **厚労省サイト**: 公的・公開サイトで利用規約緩めだが、念のためアクセス間隔 3 秒以上。3 段階画面遷移（GICB101010 → GICB102030 → GICB102060）を Playwright で再現。

---

## 9. 依頼者の意思決定ポイント

ユーザーは前回 *「次に何をしますか？」* に対して **「PoCを実行して検証」「厚労省サイト連携を追加」「ドライランモード+テスト追加」「簡易Web UI追加」** の4択を提示した直後に、別ターミナルへ作業を移したい意向を表明。

新セッション側の最初のアクションとしては、上記のオプション提示を改めて行うか、依頼者が明示した方向性を聞いてから着手するのが安全。

---

## 10. 参考: 過去のやり取りの要点

- 5/7 ミーティングで「パートナーセールス → 直接攻撃」に方針転換
- 福井氏が「来週中にシステム担当に確認して回答」と約束
- 高屋氏のターゲット: 製造業の求人を求人ボックス・Indeed に掲載中の人材紹介・派遣会社
- 例として挙がった企業: JHR株式会社、ホワイトキャリアエージェント等

詳細は `feasibility-report.md` § 1 を参照。
