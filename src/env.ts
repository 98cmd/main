import type { AppDB } from "./db";

export interface Env {
  DB: DurableObjectNamespace<AppDB>;
  GOOGLE_CLIENT_ID?: string;
  GOOGLE_CLIENT_SECRET?: string;
  /** ログインを許可するGoogleアカウント(カンマ区切り)。未設定なら初回ログインした人がオーナーになる */
  ALLOWED_EMAILS?: string;
  /** テスト用: Google APIのエンドポイント差し替え */
  GOOGLE_AUTH_BASE?: string;
  GOOGLE_TOKEN_URL?: string;
  GOOGLE_API_BASE?: string;
  /** "1" でテスト用シードルートを有効化(本番では設定しない) */
  DEV_MODE?: string;
}
