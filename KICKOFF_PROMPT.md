# 別セッションへの起動プロンプト

別ターミナル / 別 Claude セッションを立ち上げたら、以下を **そのままコピペ** して投げる。
これだけで前回のコンテキストを引き継いで作業を再開できる。

---

## コピペ用プロンプト（ここから下を全選択 → 貼り付け）

```
このリポジトリで進行中の案件を引き継ぎます。まず以下を順に実行してください。

1. ブランチを確認・切り替え
   git branch --show-current
   現在のブランチが claude/review-system-requirements-FfPKg でなければ切り替える。
   （別マシンで開いたなら `git fetch && git checkout claude/review-system-requirements-FfPKg && git pull` でOK）

2. HANDOFF.md を読む（このリポジトリのルートにある）
   - プロジェクトの目的・現状・次の選択肢が全部書いてある
   - 重要な制約（モデルIDは claude-opus-4-7、ブランチ固定、求人ボックス規約配慮）も書いてある

3. 関連ファイルにも目を通す
   - feasibility-report.md （福井氏向けの実現可能性レポート）
   - poc/README.md （PoC の使い方）
   - poc/main.py / poc/kyujinbox_poc/*.py （PoC 本体）

4. 把握できたら、HANDOFF.md §6 の「次の選択肢」（A〜F）を提示して、
   どれを進めるか私（ユーザー）に確認してください。

注意:
- このブランチ以外には push しないこと
- Cloudflare Workers のビルド失敗は無関係（無視してOK）
- 求人ボックスへの実アクセスはアクセス間隔5秒・10件キャップを守る
- フォーム自動送信は意図的に未実装（法務確認待ち）
```

---

## どこに HANDOFF.md があるか分からない場合

もし新しいターミナルが別ディレクトリで立ち上がっていて HANDOFF.md が見つからないなら、上記プロンプトに以下を追記:

```
リポジトリは GitHub の 98cmd/main、ブランチは claude/review-system-requirements-FfPKg。
ローカルにクローンが無ければ:
  git clone <リポジトリURL> && cd main
  git checkout claude/review-system-requirements-FfPKg
  cat HANDOFF.md
```
