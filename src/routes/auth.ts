import { Hono } from "hono";
import type { Env } from "../env";
import { buildAuthUrl, decodeIdToken, exchangeCode, listCalendars } from "../google";
import {
  clearSessionCookie,
  currentUser,
  dbStub,
  readStateCookie,
  setSessionCookie,
  setStateCookie,
} from "../session";
import { randomToken } from "../util";
import { loginPage, setupPage } from "../views/host";
import { messagePage } from "../views/public";

export const authRoutes = new Hono<{ Bindings: Env }>();

function allowedEmails(env: Env): string[] | null {
  if (!env.ALLOWED_EMAILS) return null;
  return env.ALLOWED_EMAILS.split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
}

authRoutes.get("/auth/login", async (c) => {
  const origin = new URL(c.req.url).origin;
  if (!c.env.GOOGLE_CLIENT_ID || !c.env.GOOGLE_CLIENT_SECRET) {
    return c.html(setupPage(`${origin}/auth/callback`));
  }
  const state = randomToken();
  await setStateCookie(c, state);
  return c.redirect(buildAuthUrl(c.env, origin, state));
});

authRoutes.get("/auth/callback", async (c) => {
  const origin = new URL(c.req.url).origin;
  const code = c.req.query("code");
  const state = c.req.query("state");
  const cookieState = readStateCookie(c);
  if (!code || !state || state !== cookieState) {
    return c.html(loginPage("ログインに失敗しました(state不一致)。もう一度お試しください。"), 400);
  }

  const tokens = await exchangeCode(c.env, origin, code);
  if (!tokens.id_token) {
    return c.html(loginPage("Googleからの応答が不正です。"), 502);
  }
  const profile = decodeIdToken(tokens.id_token);

  const db = dbStub(c.env);
  const now = Date.now();
  const result = await db.loginUser({
    email: profile.email,
    name: profile.name,
    picture: profile.picture,
    refreshToken: tokens.refresh_token ?? null,
    accessToken: tokens.access_token,
    tokenExpiresAt: now + tokens.expires_in * 1000,
    allowedEmails: allowedEmails(c.env),
    now,
  });
  if (!result.ok) {
    return c.html(
      loginPage("このアカウントではログインできません(オーナーのアカウントでログインしてください)。"),
      403,
    );
  }

  // 初回ログイン時: メインカレンダーを空き判定・登録先のデフォルトに設定
  const busyCount = (await db.query(
    "SELECT COUNT(*) AS c FROM busy_calendars WHERE user_id = ?",
    [result.userId],
  )) as { c: number }[];
  if (busyCount[0].c === 0) {
    try {
      const cals = await listCalendars(c.env, tokens.access_token);
      const primary = cals.find((cal) => cal.primary);
      if (primary) {
        await db.query(
          "INSERT OR IGNORE INTO busy_calendars (user_id, calendar_id, summary) VALUES (?, ?, ?)",
          [result.userId, primary.id, primary.summary],
        );
        await db.query(
          "UPDATE users SET booking_calendar_id = COALESCE(booking_calendar_id, ?) WHERE id = ?",
          [primary.id, result.userId],
        );
      }
    } catch {
      // カレンダー取得に失敗しても設定画面から選び直せるので握りつぶす
    }
  }

  const secret = await db.getOrCreateSecret();
  await setSessionCookie(c, secret, result.sessionId);
  return c.redirect("/dashboard");
});

authRoutes.post("/auth/logout", async (c) => {
  const user = await currentUser(c);
  if (user) {
    await dbStub(c.env).query("DELETE FROM sessions WHERE user_id = ?", [user.id]);
  }
  clearSessionCookie(c);
  return c.redirect("/");
});

authRoutes.get("/", async (c) => {
  const user = await currentUser(c);
  if (user) return c.redirect("/dashboard");
  const origin = new URL(c.req.url).origin;
  if (!c.env.GOOGLE_CLIENT_ID || !c.env.GOOGLE_CLIENT_SECRET) {
    return c.html(setupPage(`${origin}/auth/callback`));
  }
  return c.html(loginPage());
});

authRoutes.get("/healthz", (c) => c.json({ ok: true }));

authRoutes.notFound((c) =>
  c.html(messagePage("ページが見つかりません", "URLをご確認ください。"), 404),
);
