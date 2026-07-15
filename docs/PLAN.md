# 日程調整ツール 開発プラン

個人用の日程調整ツール(Spirライク)の開発計画。Googleカレンダー連携で外部の相手との1対1日程調整を効率化し、**用途別リンクのクイック発行(経由情報は相手に非表示)** を差別化ポイントとする。

---

## 1. 競合調査サマリ

### Spir(スピア)

- Google / Outlook カレンダーと双方向同期し、空き時間を自動抽出
- **空き時間リンク**: 自分の空き時間を抽出した予約ページURLを発行して相手に共有
- **候補提案型**: カレンダーから候補日時を選んでメール文面に貼り付ける方式もサポート
- 予定確定時に Web会議URL(Google Meet / Zoom / Teams)を自動発行し、確定メール送付 + 双方のカレンダーに自動登録
- チーム調整: 複数メンバーの「誰か1人が空いている」枠の自動抽出

### TimeRex(参考: 経由計測の実装方式)

- 日程調整URLに **URLパラメータで流入元や顧客IDなどの「ゲストに表示されない値」を付与**できる(最大25個のカスタムパラメータ)
- Google Analytics 連携、Google/Meta 広告のコンバージョンタグ設置に対応
- ⚠️ ただし TimeRex 方式は「URLパラメータに経由情報が載る」ため、URLを見れば相手に経由がバレる。**本ツールではスラッグ(ランダムID)にサーバー側で経由を紐付け、URL自体から経由が読み取れない設計にする**(後述)

### Cal.com(参考: OSS実装)

- OSSの日程調整基盤(Calendly代替)。Google Calendar / Meet 連携、buffer、round-robin 等フル機能
- セルフホストには PostgreSQL + Google OAuth アプリ設定が必要
- スロット計算ロジックや Google Calendar API の使い方の**実装リファレンスとして参照価値が高い**

### 方針判断: 自作 vs Cal.com セルフホスト

| | 自作 (推奨) | Cal.com セルフホスト |
|---|---|---|
| 用途別リンク+経由秘匿 | 要件どおり自由に設計できる | hidden fields で近いことは可能だがURL依存 |
| 運用コスト | Vercel + 無料DB でほぼ0円 | 常時稼働サーバー + DB が必要 |
| 実装コスト | MVPで数日〜 | 構築自体は1日だがカスタマイズが重い |
| 個人利用フィット | ◎ | △(多機能すぎる) |

→ **自作を推奨**。コア要件(経由の秘匿トラッキング)が既存ツールでは中途半端にしか実現できず、個人利用なら自作のほうが軽くて安い。

---

## 2. 機能要件

### MVP (Phase 1)

1. **Googleアカウント連携**
   - Google OAuth でログイン + Calendar スコープ取得
   - 複数カレンダーの free/busy を空き判定に利用(仕事用 + 個人用など)
2. **予約ページ(空き時間リンク)**
   - イベントタイプ(例: 「30分打ち合わせ」「60分商談」)ごとに、稼働時間・所要時間・前後バッファ・最短予約可能時刻(例: 12時間後以降)・1日の上限を設定
   - ゲストはカレンダーUIから空き枠を選択(ゲストのタイムゾーン自動判定)
3. **用途別リンクのクイック発行** ← 差別化ポイント
   - イベントタイプを選び「経由メモ」(例: `〇〇さん紹介` `X経由` `イベントLP`)を入力するだけで、ランダムスラッグの専用URLを即発行
   - `https://<domain>/b/aB3xK9` のような URL。**経由情報はDB上でスラッグに紐付くだけで、URL・予約ページのHTML・確定メールのどこにも露出しない**
   - リンクごとに有効期限・無効化・上限予約数を設定可能
4. **予約確定処理**
   - Google Calendar にイベント作成(ゲストを attendee に追加)
   - **Google Meet URL を自動発行**(Calendar API の `conferenceData` / `conferenceDataVersion=1`)
   - 双方に確定メール送信(ゲスト宛には経由情報を含めない)
5. **ダッシュボード**
   - 予約一覧(経由ラベル付き)・リンク一覧・経由別の予約数集計

### Phase 2 (Spir同等機能の拡充)

- リスケ・キャンセル用リンク(確定メールに記載)
- 候補提案型: 空き枠から候補を選んでメール貼り付け用テキストを生成
- カスタム質問フォーム(予約時に会社名・議題などを収集)
- リマインドメール(前日/1時間前)
- 予約ページのプロフィール表示(名前・写真・自己紹介)
- 祝日除外(Google の日本の祝日カレンダー参照)

### Phase 3 (発展)

- 投票型(複数候補を提示してゲストが選ぶ・複数ゲスト対応)
- Slack / Webhook 通知
- 経由別の分析ダッシュボード(コンバージョン率など)
- 予約ページのサイト埋め込みウィジェット

---

## 3. 技術スタック

> **2026-07-15 更新**: 当初案は Next.js + Vercel + PostgreSQL だったが、
> このリポジトリには Cloudflare Workers の自動デプロイ(mainブランチ)が既に構成されており、
> (1) push だけで本番反映 (2) 外部DB契約が不要 (3) 完全無料 という理由で
> **Cloudflare Workers スタックに変更して実装した**。

| レイヤ | 技術 | 理由 |
|---|---|---|
| ランタイム | Cloudflare Workers | リポジトリに自動デプロイ構成済み。無料 |
| フレームワーク | Hono + TypeScript | Workersネイティブ。SSR + 少量のバニラJSで軽量に |
| DB | Durable Objects SQLite | 事前プロビジョニング不要・追加契約不要。単一DOで直列化されるためダブルブッキング防止も容易 |
| 認証 | 自前実装の Google OAuth (authorization code flow) | Workersで動く軽量な実装。セッションは署名付きCookie |
| Google API | REST を直接 fetch | googleapis SDK はNode依存が強くWorkersに不向き |
| UI | ハンドメイドCSS(SSR) | 個人利用に十分。ビルドパイプライン不要 |
| メール | Googleカレンダーの招待メールを利用 | events.insert の sendUpdates=all で招待・リマインドともGoogleが送るため外部メールサービス不要 |
| 日時処理 | Intl API(自前ユーティリティ) | Workersで動作。外部ライブラリ不要 |

### Google Cloud 側の準備

- GCP プロジェクト作成 → Calendar API 有効化
- OAuth 同意画面: スコープは `calendar.events` + `calendar.freebusy`(または `calendar.readonly` + events)
- **個人利用なら「テスト」モードのままでOK**(テストユーザーに自分を登録すれば審査不要。restricted scope の審査を回避できる)

---

## 4. データモデル

```
User            … 自分(ホスト)。Google OAuth トークン(refresh token)を保持
CalendarAccount … 連携カレンダー。busy判定に使うか / 予定作成先か のフラグ
EventType       … 調整メニュー。所要時間, バッファ, 稼働時間ルール, 最短予約時刻, 1日上限
AvailabilityRule… EventType ごとの曜日別稼働時間 (例: 月-金 10:00-18:00)
Link            … 発行リンク。slug(ランダム), event_type_id,
                   channel_label(経由: 相手に非表示), memo, expires_at, is_active, max_bookings
Booking         … 予約。link_id(→経由が辿れる), guest_name, guest_email,
                   start/end, google_event_id, meet_url, status(confirmed/canceled), cancel_token
```

### 経由(channel)の秘匿設計

- 経由情報は `Link.channel_label` として**サーバーDBのみに保存**
- ゲストに届く可能性のある場所には一切書き込まない:
  - ❌ URL パラメータ(TimeRex方式は不採用)
  - ❌ 予約ページの HTML / JS ペイロード
  - ❌ 確定メール(ゲスト宛)
  - ❌ Google Calendar イベントの title / description(ゲストが attendee なので見える)
- ホストだけが見たい場合は Calendar イベントの `extendedProperties.private` に入れる(attendee には非公開)か、ダッシュボードでのみ表示

---

## 5. コアロジック: 空き枠計算

```
1. EventType の AvailabilityRule から、直近N週間の「稼働ウィンドウ」を生成
2. Google Calendar freebusy API で全連携カレンダーの busy 区間を取得
3. 稼働ウィンドウ − busy − 既存Booking − 前後バッファ を差し引き
4. 残りを duration 刻みのスロットに分割し、最短予約時刻より前を除外
5. ゲストのタイムゾーンに変換して予約ページに表示
```

予約確定時は**再度 freebusy を確認してから**イベント作成(ダブルブッキング防止。同時アクセスはDBトランザクション + slot のユニーク制約で防ぐ)。

Meet 発行は `events.insert` に以下を付ける:

```ts
conferenceData: {
  createRequest: {
    requestId: uuid(),
    conferenceSolutionKey: { type: 'hangoutsMeet' },
  },
},
// + conferenceDataVersion: 1
```

---

## 6. 画面構成

| パス | 画面 | 認証 |
|---|---|---|
| `/dashboard` | 予約一覧・経由別集計 | 要 |
| `/event-types` | イベントタイプ管理 | 要 |
| `/links` | リンク一覧 + **クイック発行**(経由メモ入力 → 即URLコピー) | 要 |
| `/b/[slug]` | ゲスト向け予約ページ(カレンダー → フォーム → 完了) | 不要 |
| `/booking/[token]/cancel` | ゲストのキャンセル/リスケ | トークン |

クイック発行はダッシュボード最上部に常設: 「イベントタイプ選択 + 経由メモ入力 → 発行 → クリップボードにコピー」の3秒フロー。

---

## 7. マイルストーン

| Phase | 内容 | 目安 |
|---|---|---|
| 0 | GCP設定 / プロジェクト雛形 / DB・Auth.js セットアップ | 0.5日 |
| 1a | Google連携 + freebusy 空き枠計算 + イベントタイプ | 1-2日 |
| 1b | ゲスト予約ページ + 予約確定(Meet発行 + メール) | 1-2日 |
| 1c | 用途別リンク発行 + ダッシュボード集計 | 1日 |
| 2 | リスケ/キャンセル、候補提案、カスタム質問、リマインド | 2-3日 |
| 3 | 投票型、Slack通知、分析、埋め込み | 随時 |

---

## 8. リスク・注意点

- **OAuth 審査**: 公開アプリ化する場合、Calendar の sensitive scope は Google の審査が必要。個人利用ではテストモード運用で回避
- **refresh token 失効**: テストモードのトークンは7日で失効する場合がある → 同意画面を「テスト」でも publishing status の扱いに注意(実運用では internal 扱いにできない個人Gmailの場合、審査 or 定期再認証のどちらかを許容する)
- **ダブルブッキング**: 確定直前の freebusy 再チェック + DB ユニーク制約で二重予約を防ぐ
- **メール到達性**: 独自ドメイン + SPF/DKIM 設定(Resend が案内)をしないと確定メールが迷惑メール行きになりやすい
