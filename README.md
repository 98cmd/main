# 日程調整ツール

個人用のSpirライクな日程調整ツール。Cloudflare Workers 上で動作し、Googleカレンダーと連携します。

## 特徴

- **空き時間リンク**: Googleカレンダーの予定から空き枠を自動計算し、予約ページを発行
- **用途別リンクのクイック発行**: 「〇〇さん紹介」「X経由」などの経由ラベル付きリンクを3秒で発行。
  経由はランダムなURLスラッグにサーバー側でだけ紐付き、**予約ページ・URL・招待メールのどこにも表示されません**
- **Google Meet 自動発行**: 予約確定と同時にMeet URLを発行し、ゲストへGoogleカレンダー招待を送信
- **日程変更・キャンセル**: ゲスト向けのセルフサービスリンク付き
- **候補日テキスト生成**: メール貼り付け用の候補日リストをワンクリックでコピー
- **経由別レポート**: どのチャネルから何件予約が入ったかをダッシュボードで集計

## アーキテクチャ

| レイヤ | 技術 |
|---|---|
| ランタイム | Cloudflare Workers(mainブランチへのpushで自動デプロイ) |
| フレームワーク | Hono(SSR + 少量のバニラJS) |
| データベース | Durable Objects SQLite(外部DB契約不要) |
| カレンダー/会議 | Google Calendar API(freeBusy / events + Meet) |
| 通知メール | Googleカレンダーの招待メールを利用(外部メールサービス不要) |

## セットアップ

### 1. Google Cloud の設定

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. 「APIとサービス → ライブラリ」で **Google Calendar API** を有効化
3. 「OAuth同意画面」を作成
   - User Type: **外部** / 公開ステータス: **テスト** のままでOK(審査不要)
   - テストユーザーに自分のGmailアドレスを追加
4. 「認証情報 → OAuthクライアントID(Webアプリケーション)」を作成
   - 承認済みリダイレクトURI: `https://<あなたのWorkerドメイン>/auth/callback`
     (例: `https://main.<account>.workers.dev/auth/callback`)

> **注意**: 公開ステータスが「テスト」の場合、リフレッシュトークンは7日で失効します。
> 期限切れになったら設定画面の「Googleと再連携する」からログインし直してください。
> 恒久運用したい場合はOAuth同意画面を「本番」に公開します(Calendarスコープは審査対象)。

### 2. シークレットの設定

```sh
npx wrangler secret put GOOGLE_CLIENT_ID
npx wrangler secret put GOOGLE_CLIENT_SECRET
```

Cloudflareダッシュボード(Workers → main → Settings → Variables and Secrets)からも設定できます。

任意: ログインを特定アカウントに限定する場合は `ALLOWED_EMAILS`(カンマ区切り)を設定。
未設定の場合は**初回にログインした人がオーナー**になり、以降ほかのアカウントではログインできません。

### 3. デプロイ

mainブランチにpushすると Workers Builds が自動デプロイします。手動の場合:

```sh
npm install
npm run deploy
```

### 4. 初回ログイン

デプロイ先のURLを開き「Googleでログイン」→ カレンダー権限を許可。
メインカレンダーが自動で「空き判定」と「予定の登録先」に設定されます(設定画面で変更可)。

## 使い方

1. **調整メニュー**で「30分打ち合わせ」などのメニューを作成(受付曜日・時間帯・バッファなど)
2. **ダッシュボード**のクイック発行で経由ラベルを入れてリンクを発行 → URLをコピーして相手に送付
3. ゲストが枠を選んで予約すると、Meet付きの予定が双方のカレンダーに登録されます
4. 予約状況と経由別の集計はダッシュボード/予約一覧で確認できます

## 開発

```sh
npm run dev    # ローカル起動(Google未設定でもセットアップ画面まで動作)
npm test       # ユニットテスト(空き枠計算・タイムゾーン)
npm run e2e    # E2E: GoogleスタブAPI + wrangler dev でフルフロー検証
npm run check  # 型チェック + デプロイのドライラン
```

E2Eは実際のGoogleアカウント不要です(`scripts/google-stub.mjs` がOAuth/Calendar APIを模擬)。

## プライバシー設計(経由ラベル)

経由ラベルが登場するのは次の2箇所だけです:

- このアプリのDB(Durable Object SQLite)
- Googleカレンダーイベントの `extendedProperties.private`(主催者のカレンダーからのみ参照可能)

ゲストに届くHTML・URL・招待メール・イベントのタイトル/説明には一切含まれません(E2Eで検証済み)。
