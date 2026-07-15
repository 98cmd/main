import type { Context } from "hono";
import { getCookie, setCookie, deleteCookie } from "hono/cookie";
import type { Env } from "./env";
import type { UserRow } from "./types";
import { hmacSign, hmacVerify } from "./util";

const SESSION_COOKIE = "sid";
const STATE_COOKIE = "oauth_state";

/** Bindings に Env を持つ任意のHonoコンテキストを受け取れるようにする */
type EnvLike = { Bindings: Env };

export function dbStub(env: Env) {
  return env.DB.get(env.DB.idFromName("main"));
}

export async function setSessionCookie<E extends EnvLike>(
  c: Context<E>,
  secret: string,
  sessionId: string,
): Promise<void> {
  const sig = await hmacSign(secret, sessionId);
  setCookie(c, SESSION_COOKIE, `${sessionId}.${sig}`, {
    httpOnly: true,
    secure: true,
    sameSite: "Lax",
    path: "/",
    maxAge: 30 * 24 * 60 * 60,
  });
}

export function clearSessionCookie<E extends EnvLike>(c: Context<E>): void {
  deleteCookie(c, SESSION_COOKIE, { path: "/" });
}

/** セッションクッキーを検証し、ログイン中のユーザーを返す */
export async function currentUser<E extends EnvLike>(
  c: Context<E>,
): Promise<UserRow | null> {
  const raw = getCookie(c, SESSION_COOKIE);
  if (!raw) return null;
  const dot = raw.lastIndexOf(".");
  if (dot <= 0) return null;
  const sessionId = raw.slice(0, dot);
  const sig = raw.slice(dot + 1);

  const db = dbStub(c.env);
  const secret = await db.getOrCreateSecret();
  if (!(await hmacVerify(secret, sessionId, sig))) return null;

  const rows = (await db.query(
    `SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
     WHERE s.id = ? AND s.expires_at > ?`,
    [sessionId, Date.now()],
  )) as unknown as UserRow[];
  return rows[0] ?? null;
}

export async function setStateCookie<E extends EnvLike>(
  c: Context<E>,
  state: string,
): Promise<void> {
  setCookie(c, STATE_COOKIE, state, {
    httpOnly: true,
    secure: true,
    sameSite: "Lax",
    path: "/",
    maxAge: 600,
  });
}

export function readStateCookie<E extends EnvLike>(c: Context<E>): string | undefined {
  const v = getCookie(c, STATE_COOKIE);
  deleteCookie(c, STATE_COOKIE, { path: "/" });
  return v;
}
