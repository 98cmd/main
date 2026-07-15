import { DurableObject } from "cloudflare:workers";
import { randomToken } from "./util";

const SCHEMA = `
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  picture TEXT,
  refresh_token TEXT,
  access_token TEXT,
  token_expires_at INTEGER,
  timezone TEXT NOT NULL DEFAULT 'Asia/Tokyo',
  booking_calendar_id TEXT,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS busy_calendars (
  user_id INTEGER NOT NULL,
  calendar_id TEXT NOT NULL,
  summary TEXT,
  PRIMARY KEY (user_id, calendar_id)
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS event_types (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  duration_min INTEGER NOT NULL DEFAULT 30,
  buffer_before_min INTEGER NOT NULL DEFAULT 0,
  buffer_after_min INTEGER NOT NULL DEFAULT 0,
  min_notice_hours INTEGER NOT NULL DEFAULT 12,
  max_per_day INTEGER,
  days_ahead INTEGER NOT NULL DEFAULT 21,
  slot_step_min INTEGER NOT NULL DEFAULT 30,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS availability_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type_id INTEGER NOT NULL,
  weekday INTEGER NOT NULL,
  start_min INTEGER NOT NULL,
  end_min INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  event_type_id INTEGER NOT NULL,
  channel_label TEXT NOT NULL DEFAULT '',
  memo TEXT NOT NULL DEFAULT '',
  is_active INTEGER NOT NULL DEFAULT 1,
  expires_at INTEGER,
  max_bookings INTEGER,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  link_id INTEGER NOT NULL,
  event_type_id INTEGER NOT NULL,
  guest_name TEXT NOT NULL,
  guest_email TEXT NOT NULL,
  guest_note TEXT NOT NULL DEFAULT '',
  guest_tz TEXT NOT NULL DEFAULT 'Asia/Tokyo',
  start_ts INTEGER NOT NULL,
  end_ts INTEGER NOT NULL,
  guard_start INTEGER NOT NULL,
  guard_end INTEGER NOT NULL,
  host_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  google_event_id TEXT,
  calendar_id TEXT,
  meet_url TEXT,
  cancel_token TEXT UNIQUE NOT NULL,
  created_at INTEGER NOT NULL,
  canceled_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_bookings_time ON bookings (status, start_ts);
`;

/** 確定処理中(pending)の予約をブロック対象として扱う猶予時間 */
const PENDING_TTL_MS = 10 * 60 * 1000;

type Param = string | number | null;

/** RPC越しに返せるよう、値をJSON互換型に限定した行型 */
export type Row = Record<string, string | number | null>;

export interface LoginInput {
  email: string;
  name: string | null;
  picture: string | null;
  refreshToken: string | null;
  accessToken: string | null;
  tokenExpiresAt: number | null;
  /** 環境変数で許可リストが指定されている場合はそれを優先 */
  allowedEmails: string[] | null;
  now: number;
}

export type LoginResult =
  | { ok: true; userId: number; sessionId: string }
  | { ok: false; reason: "forbidden" };

export interface ReserveInput {
  userId: number;
  linkId: number;
  eventTypeId: number;
  guestName: string;
  guestEmail: string;
  guestNote: string;
  guestTz: string;
  start: number;
  end: number;
  /** バッファを含めた占有範囲(この範囲で重複判定する) */
  guardStart: number;
  guardEnd: number;
  hostDate: string;
  maxPerDay: number | null;
  linkMaxBookings: number | null;
  now: number;
}

export type ReserveResult =
  | { ok: true; bookingId: number; cancelToken: string }
  | { ok: false; reason: "slot_taken" | "day_full" | "link_full" };

export class AppDB extends DurableObject {
  private sql: SqlStorage;

  constructor(ctx: DurableObjectState, env: unknown) {
    super(ctx, env as never);
    this.sql = ctx.storage.sql;
    ctx.blockConcurrencyWhile(async () => {
      this.sql.exec(SCHEMA);
    });
  }

  /** 汎用クエリ。DOはシングルスレッドなので1回の呼び出しはアトミック */
  query(sqlText: string, params: Param[] = []): Row[] {
    return this.sql.exec(sqlText, ...params).toArray() as Row[];
  }

  /** セッション署名用シークレット。初回アクセス時に生成して永続化 */
  getOrCreateSecret(): string {
    const rows = this.sql
      .exec("SELECT value FROM settings WHERE key = 'session_secret'")
      .toArray();
    if (rows.length > 0) return rows[0].value as string;
    const secret = randomToken() + randomToken();
    this.sql.exec(
      "INSERT INTO settings (key, value) VALUES ('session_secret', ?)",
      secret,
    );
    return secret;
  }

  /**
   * Googleログイン処理。個人ツールなので「初回ログインした人がオーナー」方式:
   * 許可リスト(env)があればそれに従い、なければ最初に登録された1人だけを許可する。
   */
  loginUser(input: LoginInput): LoginResult {
    const existing = this.sql
      .exec("SELECT id, email FROM users WHERE email = ?", input.email)
      .toArray();

    if (input.allowedEmails) {
      if (!input.allowedEmails.includes(input.email.toLowerCase())) {
        return { ok: false, reason: "forbidden" };
      }
    } else if (existing.length === 0) {
      const count = this.sql
        .exec("SELECT COUNT(*) AS c FROM users")
        .one().c as number;
      if (count > 0) return { ok: false, reason: "forbidden" };
    }

    let userId: number;
    if (existing.length > 0) {
      userId = existing[0].id as number;
      this.sql.exec(
        `UPDATE users SET name = ?, picture = ?, access_token = ?, token_expires_at = ?,
           refresh_token = COALESCE(?, refresh_token)
         WHERE id = ?`,
        input.name,
        input.picture,
        input.accessToken,
        input.tokenExpiresAt,
        input.refreshToken,
        userId,
      );
    } else {
      this.sql.exec(
        `INSERT INTO users (email, name, picture, refresh_token, access_token, token_expires_at, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        input.email,
        input.name,
        input.picture,
        input.refreshToken,
        input.accessToken,
        input.tokenExpiresAt,
        input.now,
      );
      userId = this.sql.exec("SELECT last_insert_rowid() AS id").one()
        .id as number;
    }

    const sessionId = randomToken();
    const thirtyDays = 30 * 24 * 60 * 60 * 1000;
    this.sql.exec(
      "INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)",
      sessionId,
      userId,
      input.now + thirtyDays,
    );
    this.sql.exec("DELETE FROM sessions WHERE expires_at < ?", input.now);
    return { ok: true, userId, sessionId };
  }

  /**
   * 予約枠の確保。重複・上限チェックと挿入を1回のRPCで行うことで
   * ダブルブッキングを防ぐ(DOへのリクエストは直列化される)。
   */
  reserveBooking(input: ReserveInput): ReserveResult {
    // 確定処理が失敗したまま残った古いpendingを掃除
    this.sql.exec(
      "DELETE FROM bookings WHERE status = 'pending' AND created_at < ?",
      input.now - PENDING_TTL_MS,
    );

    // 既存予約側のバッファ(guard_start/guard_end)と新規予約側のバッファの両方を尊重して重複判定
    const overlap = this.sql
      .exec(
        `SELECT COUNT(*) AS c FROM bookings b
         JOIN event_types et ON et.id = b.event_type_id
         WHERE et.user_id = ? AND b.status IN ('pending', 'confirmed')
           AND b.guard_start < ? AND b.guard_end > ?`,
        input.userId,
        input.guardEnd,
        input.guardStart,
      )
      .one().c as number;
    if (overlap > 0) return { ok: false, reason: "slot_taken" };

    if (input.maxPerDay != null) {
      const dayCount = this.sql
        .exec(
          `SELECT COUNT(*) AS c FROM bookings
           WHERE status IN ('pending', 'confirmed') AND event_type_id = ? AND host_date = ?`,
          input.eventTypeId,
          input.hostDate,
        )
        .one().c as number;
      if (dayCount >= input.maxPerDay) return { ok: false, reason: "day_full" };
    }

    if (input.linkMaxBookings != null) {
      const linkCount = this.sql
        .exec(
          `SELECT COUNT(*) AS c FROM bookings
           WHERE status IN ('pending', 'confirmed') AND link_id = ?`,
          input.linkId,
        )
        .one().c as number;
      if (linkCount >= input.linkMaxBookings) {
        return { ok: false, reason: "link_full" };
      }
    }

    const cancelToken = randomToken();
    this.sql.exec(
      `INSERT INTO bookings
         (link_id, event_type_id, guest_name, guest_email, guest_note, guest_tz,
          start_ts, end_ts, guard_start, guard_end, host_date, status, cancel_token, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)`,
      input.linkId,
      input.eventTypeId,
      input.guestName,
      input.guestEmail,
      input.guestNote,
      input.guestTz,
      input.start,
      input.end,
      input.guardStart,
      input.guardEnd,
      input.hostDate,
      cancelToken,
      input.now,
    );
    const bookingId = this.sql.exec("SELECT last_insert_rowid() AS id").one()
      .id as number;
    return { ok: true, bookingId, cancelToken };
  }

  confirmBooking(
    bookingId: number,
    googleEventId: string,
    meetUrl: string | null,
    calendarId: string,
  ): void {
    this.sql.exec(
      "UPDATE bookings SET status = 'confirmed', google_event_id = ?, meet_url = ?, calendar_id = ? WHERE id = ?",
      googleEventId,
      meetUrl,
      calendarId,
      bookingId,
    );
  }

  /** カレンダー登録に失敗した予約を破棄 */
  discardBooking(bookingId: number): void {
    this.sql.exec("DELETE FROM bookings WHERE id = ? AND status = 'pending'", bookingId);
  }

  cancelBooking(bookingId: number, now: number): void {
    this.sql.exec(
      "UPDATE bookings SET status = 'canceled', canceled_at = ? WHERE id = ? AND status = 'confirmed'",
      now,
      bookingId,
    );
  }

  /** INSERTと採番IDの取得を1回のRPCで行う(並行リクエストとの取り違え防止) */
  insertReturningId(sqlText: string, params: Param[] = []): number {
    this.sql.exec(sqlText, ...params);
    return this.sql.exec("SELECT last_insert_rowid() AS id").one().id as number;
  }
}
