import { Hono } from "hono";
import type { Env } from "../env";
import type { AppDB } from "../db";
import type { BookingRow, EventTypeRow, LinkRow, UserRow } from "../types";
import { dbStub } from "../session";
import { dateKey } from "../tz";
import { slotsForEventType } from "../service";
import { deleteEvent, getValidAccessToken, insertEvent } from "../google";
import { cancelPage, guestBookingPage, messagePage } from "../views/public";

export const publicRoutes = new Hono<{ Bindings: Env }>();

interface LinkContext {
  link: LinkRow;
  et: EventTypeRow;
  user: UserRow;
}

/** 予約リンクの有効性チェック。経由情報(channel_label)はこの層より外に出さない */
async function loadLinkContext(
  db: DurableObjectStub<AppDB>,
  slug: string,
): Promise<LinkContext | null> {
  const links = (await db.query("SELECT * FROM links WHERE slug = ?", [
    slug,
  ])) as unknown as LinkRow[];
  const link = links[0];
  if (!link || !link.is_active) return null;
  if (link.expires_at != null && link.expires_at < Date.now()) return null;

  if (link.max_bookings != null) {
    const count = (await db.query(
      "SELECT COUNT(*) AS c FROM bookings WHERE link_id = ? AND status IN ('pending','confirmed')",
      [link.id],
    )) as { c: number }[];
    if (count[0].c >= link.max_bookings) return null;
  }

  const ets = (await db.query(
    "SELECT * FROM event_types WHERE id = ? AND is_active = 1",
    [link.event_type_id],
  )) as unknown as EventTypeRow[];
  if (ets.length === 0) return null;

  const users = (await db.query("SELECT * FROM users WHERE id = ?", [
    ets[0].user_id,
  ])) as unknown as UserRow[];
  if (users.length === 0) return null;

  return { link, et: ets[0], user: users[0] };
}

const LINK_CLOSED = messagePage(
  "このリンクは利用できません",
  "リンクが無効になったか、受付を終了しました。お手数ですが主催者にご確認ください。",
);

publicRoutes.get("/b/:slug", async (c) => {
  const db = dbStub(c.env);
  const ctx = await loadLinkContext(db, c.req.param("slug"));
  if (!ctx) return c.html(LINK_CLOSED, 404);

  let rescheduleToken: string | null = null;
  const rt = c.req.query("rt");
  if (rt) {
    const rows = await db.query(
      "SELECT 1 FROM bookings WHERE cancel_token = ? AND status = 'confirmed'",
      [rt],
    );
    if (rows.length > 0) rescheduleToken = rt;
  }

  return c.html(
    guestBookingPage({
      slug: ctx.link.slug,
      et: ctx.et,
      host: ctx.user,
      rescheduleToken,
    }),
  );
});

publicRoutes.get("/api/slots/:slug", async (c) => {
  const db = dbStub(c.env);
  const ctx = await loadLinkContext(db, c.req.param("slug"));
  if (!ctx) return c.json({ error: "not_found" }, 404);
  const slots = await slotsForEventType(c.env, db, ctx.user, ctx.et);
  return c.json({ slots: slots.slice(0, 1000) });
});

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

publicRoutes.post("/api/book/:slug", async (c) => {
  const db = dbStub(c.env);
  const ctx = await loadLinkContext(db, c.req.param("slug"));
  if (!ctx) return c.json({ ok: false, error: "not_found" }, 404);
  const { link, et, user } = ctx;

  const body = (await c.req.json().catch(() => null)) as {
    start?: unknown;
    name?: unknown;
    email?: unknown;
    note?: unknown;
    tz?: unknown;
    rescheduleToken?: unknown;
  } | null;
  if (!body) return c.json({ ok: false, error: "bad_request" }, 400);

  const start = Number(body.start);
  const name = String(body.name ?? "").trim().slice(0, 100);
  const email = String(body.email ?? "").trim().slice(0, 200);
  const note = String(body.note ?? "").trim().slice(0, 1000);
  let guestTz = String(body.tz ?? "Asia/Tokyo").slice(0, 50);
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: guestTz });
  } catch {
    guestTz = "Asia/Tokyo";
  }
  if (!Number.isFinite(start) || !name || !EMAIL_RE.test(email)) {
    return c.json({ ok: false, error: "bad_request" }, 400);
  }

  // 提示中の枠に含まれるかを再計算して検証(freebusyも再取得される)
  const slots = await slotsForEventType(c.env, db, user, et);
  const slot = slots.find((s) => s.start === start);
  if (!slot) return c.json({ ok: false, error: "slot_taken" }, 409);

  const reserve = await db.reserveBooking({
    userId: user.id,
    linkId: link.id,
    eventTypeId: et.id,
    guestName: name,
    guestEmail: email,
    guestNote: note,
    guestTz,
    start: slot.start,
    end: slot.end,
    guardStart: slot.start - et.buffer_before_min * 60_000,
    guardEnd: slot.end + et.buffer_after_min * 60_000,
    hostDate: dateKey(slot.start, user.timezone),
    maxPerDay: et.max_per_day,
    linkMaxBookings: link.max_bookings,
    now: Date.now(),
  });
  if (!reserve.ok) {
    const status = reserve.reason === "slot_taken" ? 409 : 409;
    return c.json({ ok: false, error: reserve.reason }, status);
  }

  const origin = new URL(c.req.url).origin;
  const cancelUrl = `${origin}/cancel/${reserve.cancelToken}`;
  const calendarId = user.booking_calendar_id ?? "primary";

  let meetUrl: string | null = null;
  try {
    const token = await getValidAccessToken(c.env, db, user);
    const result = await insertEvent(c.env, token, {
      calendarId,
      summary: `${name}様 / ${et.title}`,
      // 説明はゲストにも見えるため、経由(channel_label)は絶対に含めない
      description: [
        `ご予約者: ${name} (${email})`,
        note ? `メッセージ: ${note}` : null,
        "",
        `変更・キャンセル: ${cancelUrl}`,
      ]
        .filter((l) => l !== null)
        .join("\n"),
      start: slot.start,
      end: slot.end,
      guestEmail: email,
      guestName: name,
      channelLabel: link.channel_label,
      bookingId: reserve.bookingId,
    });
    meetUrl = result.meetUrl;
    await db.confirmBooking(reserve.bookingId, result.eventId, meetUrl, calendarId);
  } catch (e) {
    await db.discardBooking(reserve.bookingId);
    console.error("calendar insert failed", e);
    return c.json({ ok: false, error: "calendar_failed" }, 502);
  }

  // 日程変更: 新しい予約が確定できた後に元の予約を取り消す
  // (同一ホストの予約のみ対象 — 他ホストのリンクへのトークン持ち込みを防ぐ)
  const rt = body.rescheduleToken;
  if (typeof rt === "string" && rt) {
    const olds = (await db.query(
      `SELECT b.* FROM bookings b
       JOIN event_types et ON et.id = b.event_type_id
       WHERE b.cancel_token = ? AND b.status = 'confirmed' AND et.user_id = ?`,
      [rt, user.id],
    )) as unknown as BookingRow[];
    const old = olds[0];
    if (old && old.id !== reserve.bookingId) {
      try {
        if (old.google_event_id) {
          const token = await getValidAccessToken(c.env, db, user);
          await deleteEvent(
            c.env,
            token,
            old.calendar_id ?? calendarId,
            old.google_event_id,
          );
        }
      } catch (e) {
        console.error("old event delete failed", e);
      }
      await db.cancelBooking(old.id, Date.now());
    }
  }

  return c.json({ ok: true, meetUrl, cancelUrl, start: slot.start, end: slot.end });
});

publicRoutes.get("/cancel/:token", async (c) => {
  const db = dbStub(c.env);
  const rows = (await db.query(
    `SELECT b.*, et.title AS et_title, l.slug AS slug
     FROM bookings b
     JOIN event_types et ON et.id = b.event_type_id
     JOIN links l ON l.id = b.link_id
     WHERE b.cancel_token = ?`,
    [c.req.param("token")],
  )) as unknown as (BookingRow & { et_title: string; slug: string })[];
  const b = rows[0];
  if (!b || b.status === "pending") {
    return c.html(messagePage("予約が見つかりません", "URLをご確認ください。"), 404);
  }
  return c.html(
    cancelPage({ booking: b, etTitle: b.et_title, slug: b.slug, guestTz: b.guest_tz }),
  );
});

publicRoutes.post("/cancel/:token", async (c) => {
  const db = dbStub(c.env);
  const rows = (await db.query(
    "SELECT * FROM bookings WHERE cancel_token = ? AND status = 'confirmed'",
    [c.req.param("token")],
  )) as unknown as BookingRow[];
  const b = rows[0];
  if (!b) {
    return c.html(messagePage("予約が見つかりません", "すでにキャンセル済みの可能性があります。"), 404);
  }

  const ets = (await db.query("SELECT * FROM event_types WHERE id = ?", [
    b.event_type_id,
  ])) as unknown as EventTypeRow[];
  const users = ets.length
    ? ((await db.query("SELECT * FROM users WHERE id = ?", [
        ets[0].user_id,
      ])) as unknown as UserRow[])
    : [];

  let calendarDeleted = true;
  if (b.google_event_id && users[0]) {
    try {
      const token = await getValidAccessToken(c.env, db, users[0]);
      await deleteEvent(
        c.env,
        token,
        b.calendar_id ?? users[0].booking_calendar_id ?? "primary",
        b.google_event_id,
      );
    } catch (e) {
      calendarDeleted = false;
      console.error("event delete failed", e);
    }
  }
  await db.cancelBooking(b.id, Date.now());
  return c.html(
    messagePage(
      "キャンセルしました",
      calendarDeleted
        ? "予約をキャンセルしました。カレンダーの予定も削除されます。"
        : "予約をキャンセルしましたが、カレンダーの予定の削除に失敗した可能性があります。予定が残っている場合は主催者にご連絡ください。",
    ),
  );
});
