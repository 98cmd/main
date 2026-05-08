# 別セッションへの起動プロンプト（5/9 更新版）

別ターミナル / 別 Claude セッションを立ち上げたら、以下を **そのままコピペ** して投げる。

---

## コピペ用プロンプト（ここから下を全選択 → 貼り付け）

```
このリポジトリで進行中の案件を引き継ぎます。GitHub: https://github.com/98cmd/main / ブランチ: claude/review-system-requirements-FfPKg / PR #2 (Ready for review)。

1. 環境準備
   既存 clone があれば:
     cd <既存パス>
     git fetch origin
     git checkout claude/review-system-requirements-FfPKg
     git pull
   無ければ:
     git clone https://github.com/98cmd/main.git
     cd main
     git checkout claude/review-system-requirements-FfPKg

2. HANDOFF.md を熟読（最新更新: 2026-05-09）
   - § 4 完了済タスク（5/8 PoC 検証 / 5/9 cross_filter 実装と実測）
   - § 6 次の選択肢 A〜G
   - § 8 重要な制約（モデル ID / 規約 / API キーの扱い）

3. 関連ファイルにも目を通す
   - feasibility-report.md (§9 に実証結果)
   - poc/README.md
   - poc/main.py / poc/cross_filter.py
   - poc/kyujinbox_poc/scraper.py / extractor.py / mhlw.py / mynavi.py / wantedly.py
   - poc/build_html.py / build_html_leads.py
   - poc/output/leads.html (最新の cross_filter 結果)
   - poc/output/unmatched_leads.json (リード生データ)

4. 把握できたら、HANDOFF.md §6 の選択肢 A〜G を提示して、
   どれを進めるか私（ユーザー）に確認してください。
   特に Wantedly のリード率 35% が高いため、A（Wantedly 100 件）→ E（営業文章生成）の組み合わせが第一候補。

5. 5/9 時点までの実測値（次に着手する判断材料）
   - 求人ボックス代理店 cliant: UPDRAFT 高屋氏（PRES 福井氏経由）
   - モデル: claude-sonnet-4-6 既定（Opus 4.7 比 1/5 コスト）
   - 求人ボックス内サンプル: 14 ユニーク社（製造系人材紹介・派遣）
   - マイナビ→求人ボックス突合: 30 件、MISSING 2 件 (リード率 7%)
   - Wantedly→求人ボックス突合: 17 件、MISSING 6 件 (リード率 35%)
   - 求人ボックス提携媒体: 94 媒体すべて中小・ATS 系
     主要転職媒体（doda / マイナビ / リクナビ / en / ビズリーチ / Wantedly / type / Forkwell / LinkedIn / Indeed）は 0 件提携
   - 厚労省連携で許可番号・住所・電話の取得率 80% 達成

注意:
- このブランチ以外には push しないこと（HANDOFF.md §2 制約）
- 求人ボックスへの実アクセスはアクセス間隔 5 秒・件数キャップ
- 厚労省は 3 秒間隔
- フォーム自動送信は意図的に未実装（法務確認待ち）
- ANTHROPIC_API_KEY は恒久 env に置かない（CLAUDE.md ルール）。
  ANTHROPIC_API_KEY_SCRIPTS 別名 → main.py のフォールバックで読まれる。
- doda は Cloudflare 系保護で全アクセス不可。playwright firefox / 別 proxy 経由が必要なら別途調査。
```

---

## どこに HANDOFF.md があるか分からない場合

新しいターミナルで HANDOFF.md が見つからないなら、上記プロンプトに以下を追記:

```
リポジトリは GitHub の 98cmd/main、ブランチは claude/review-system-requirements-FfPKg。
ローカルにクローンが無ければ:
  git clone https://github.com/98cmd/main.git
  cd main
  git checkout claude/review-system-requirements-FfPKg
  cat HANDOFF.md
```
