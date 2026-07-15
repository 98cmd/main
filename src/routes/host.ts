import { Hono } from "hono";
import type { Context } from "hono";
import type { Env } from "../env";
import type { AppDB } from "../db";
import type { BookingRow, EventTypeRow, LinkRow, RuleRow, UserRow } from "../types";
import { currentUser, dbStub } from "../session";
import { randomSlug } from "../util";
import { hhmmToMin } from "../fmt";
import { getValidAccessToken, listCalendars, GoogleApiError } from "../google";
import { slotsForEventType } from "../service";
import {
  bookingsPage,
  candidatesPage,
  dashboardPage,
  eventTypeFormPage,
  eventTypesPage,
  linksPage,
  settingsPage,
} from "../views/host";
import { messagePage } from "../views/public";

type Vars = { user: UserRow };

export const hostRoutes = new Hono<{ Bindings: Env; Variables: Vars }>();

const PROTECTED_PATHS = [
  "/dashboard",
  "/links",
  "/links/*",
  "/bookings",
  "/event-types",
  "/event-types/*",
  "/settings",
];
for (const path of PROTECTED_PATHS) {
  hostRoutes.use(path, async (c, next) => {
    const user = await currentUser(c);
    if (!user) return c.redirect("/");
    c.set("user", user);
    await next();
  });
}

function origin(c: { req: { url: string } }): string {
  return new URL(c.req.url).origin;
}

async function activeEventTypes(
  db: DurableObjectStub<AppDB>,
  userId: number,
): Promise<EventTypeRow[]> {
  return (await db.query(
    "SELECT * FROM event_types WHERE user_id = ? AND is_active = 1 ORDER BY created_at",
    [userId],
  )) as unknown as EventTypeRow[];
}

async function issuedLink(
  c: { req: { query: (k: string) => string | undefined } },
  db: DurableObjectStub<AppDB>,
  userId: number,
): Promise<LinkRow | null> {
  const slug = c.req.query("issued");
  if (!slug) return null;
  const rows = (await db.query(
    `SELECT l.* FROM links l JOIN event_types et ON et.id = l.event_type_id
     WHERE l.slug = ? AND et.user_id = ?`,
    [slug, userId],
  )) as unknown as LinkRow[];
  return rows[0] ?? null;
}

/* ---------- ダッシュボード ---------- */

hostRoutes.get("/dashboard", async (c) => {
  const user = c.get("user");
  const db = dbStub(c.env);
  const now = Date.now();

  const upcoming = (await db.query(
    `SELECT b.*, l.channel_label, et.title AS et_title
     FROM bookings b
     JOIN links l ON l.id = b.link_id
     JOIN event_types et ON et.id = b.event_type_id
     WHERE et.user_id = ? AND b.status = 'confirmed' AND b.end_ts >= ?
     ORDER BY b.start_ts LIMIT 8`,
    [user.id, now],
  )) as unknown as (BookingRow & { channel_label: string; et_title: string })[];

  const channelStats = (await db.query(
    `SELECT l.channel_label, COUNT(*) AS count
     FROM bookings b
     JOIN links l ON l.id = b.link_id
     JOIN event_types et ON et.id = b.event_type_id
     WHERE et.user_id = ? AND b.status = 'confirmed'
     GROUP BY l.channel_label ORDER BY count DESC`,
    [user.id],
  )) as unknown as { channel_label: string; count: number }[];

  const busyCount = (await db.query(
    "SELECT COUNT(*) AS c FROM busy_calendars WHERE user_id = ?",
    [user.id],
  )) as { c: number }[];

  return c.html(
    dashboardPage({
      user,
      origin: origin(c),
      eventTypes: await activeEventTypes(db, user.id),
      issuedLink: await issuedLink(c, db, user.id),
      upcoming,
      channelStats,
      needsCalendarSetup: busyCount[0].c === 0,
    }),
  );
});

/* ---------- リンク ---------- */

hostRoutes.get("/links", async (c) => {
  const user = c.get("user");
  const db = dbStub(c.env);
  const links = (await db.query(
    `SELECT l.*, et.title AS et_title,
       (SELECT COUNT(*) FROM bookings b WHERE b.link_id = l.id AND b.status = 'confirmed') AS booking_count
     FROM links l JOIN event_types et ON et.id = l.event_type_id
     WHERE et.user_id = ?
     ORDER BY l.created_at DESC`,
    [user.id],
  )) as unknown as (LinkRow & { et_title: string; booking_count: number })[];

  return c.html(
    linksPage({
      origin: origin(c),
      eventTypes: await activeEventTypes(db, user.id),
      issuedLink: await issuedLink(c, db, user.id),
      links,
    }),
  );
});

hostRoutes.post("/links", async (c) => {
  const user = c.get("user");
  const db = dbStub(c.env);
  const body = await c.req.parseBody();
  const eventTypeId = Number(body.event_type_id);
  const channel = String(body.channel_label ?? "").trim().slice(0, 100);
  const memo = String(body.memo ?? "").trim().slice(0, 200);
  const back = body.back === "dashboard" ? "/dashboard" : "/links";

  const ets = (await db.query(
    "SELECT * FROM event_types WHERE id = ? AND user_id = ?",
    [eventTypeId, user.id],
  )) as unknown as EventTypeRow[];
  if (ets.length === 0 || !channel) return c.redirect(back);

  let slug = "";
  for (let i = 0; i < 5; i++) {
    slug = randomSlug(8);
    const dup = await db.query("SELECT 1 FROM links WHERE slug = ?", [slug]);
    if (dup.length === 0) break;
    slug = "";
  }
  if (!slug) return c.html(messagePage("エラー", "リンクの発行に失敗しました。"), 500);

  await db.query(
    "INSERT INTO links (slug, event_type_id, channel_label, memo, created_at) VALUES (?, ?, ?, ?, ?)",
    [slug, eventTypeId, channel, memo, Date.now()],
  );
  return c.redirect(`${back}?issued=${slug}`);
});

hostRoutes.post("/links/:id/toggle", async (c) => {
  const user = c.get("user");
  const db = dbStub(c.env);
  await db.query(
    `UPDATE links SET is_active = 1 - is_active
     WHERE id = ? AND event_type_id IN (SELECT id FROM event_types WHERE user_id = ?)`,
    [Number(c.req.param("id")), user.id],
  );
  return c.redirect("/links");
});

/* ---------- 予約一覧 ---------- */

hostRoutes.get("/bookings", async (c) => {
  const user = c.get("user");
  const db = dbStub(c.env);
  const bookings = (await db.query(
    `SELECT b.*, l.channel_label, et.title AS et_title
     FROM bookings b
     JOIN links l ON l.id = b.link_id
     JOIN event_types et ON et.id = b.event_type_id
     WHERE et.user_id = ? AND b.status IN ('confirmed', 'canceled')
     ORDER BY b.start_ts DESC LIMIT 200`,
    [user.id],
  )) as unknown as (BookingRow & { channel_label: string; et_title: string })[];
  return c.html(bookingsPage({ tz: user.timezone, bookings }));
});

/* ---------- 調整メニュー ---------- */

hostRoutes.get("/event-types", async (c) => {
  const user = c.get("user");
  const db = dbStub(c.env);
  const ets = (await db.query(
    "SELECT * FROM event_types WHERE user_id = ? ORDER BY created_at",
    [user.id],
  )) as unknown as EventTypeRow[];
  const withDetails = [];
  for (const et of ets) {
    const rules = (await db.query(
      "SELECT * FROM availability_rules WHERE event_type_id = ?",
      [et.id],
    )) as unknown as RuleRow[];
    const linkCount = (await db.query(
      "SELECT COUNT(*) AS c FROM links WHERE event_type_id = ? AND is_active = 1",
      [et.id],
    )) as { c: number }[];
    withDetails.push({ ...et, rules, link_count: linkCount[0].c });
  }
  return c.html(eventTypesPage({ eventTypes: withDetails }));
});

hostRoutes.get("/event-types/new", (c) =>
  c.html(eventTypeFormPage({ et: null, rules: [] })),
);

function intField(fd: FormData, name: string, def: number, min: number, max: number): number {
  const n = Number(fd.get(name));
  if (!Number.isFinite(n)) return def;
  return Math.max(min, Math.min(max, Math.round(n)));
}

async function saveEventType(
  c: Context<{ Bindings: Env; Variables: Vars }>,
  existingId: number | null,
) {
  const user = c.get("user");
  const db = dbStub(c.env);
  const fd = await c.req.raw.formData();

  const title = String(fd.get("title") ?? "").trim().slice(0, 100);
  if (!title) return c.redirect("/event-types");
  const description = String(fd.get("description") ?? "").trim().slice(0, 1000);
  const duration = intField(fd, "duration_min", 30, 5, 480);
  const step = intField(fd, "slot_step_min", 30, 5, 240);
  const daysAhead = intField(fd, "days_ahead", 21, 1, 90);
  const bufBefore = intField(fd, "buffer_before_min", 0, 0, 120);
  const bufAfter = intField(fd, "buffer_after_min", 0, 0, 120);
  const minNotice = intField(fd, "min_notice_hours", 12, 0, 168);
  const maxPerDayRaw = String(fd.get("max_per_day") ?? "").trim();
  const maxPerDay = maxPerDayRaw ? intField(fd, "max_per_day", 1, 1, 50) : null;
  const isActive = existingId === null || fd.get("is_active") === "1" ? 1 : 0;

  const startMin = hhmmToMin(String(fd.get("start_time") ?? "")) ?? 10 * 60;
  const endMin = hhmmToMin(String(fd.get("end_time") ?? "")) ?? 18 * 60;
  const weekdays = fd
    .getAll("weekday")
    .map((v) => Number(v))
    .filter((w) => Number.isInteger(w) && w >= 0 && w <= 6);

  let etId: number;
  if (existingId === null) {
    etId = await db.insertReturningId(
      `INSERT INTO event_types
         (user_id, title, description, duration_min, buffer_before_min, buffer_after_min,
          min_notice_hours, max_per_day, days_ahead, slot_step_min, is_active, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)`,
      [user.id, title, description, duration, bufBefore, bufAfter, minNotice, maxPerDay, daysAhead, step, Date.now()],
    );
  } else {
    const owned = await db.query(
      "SELECT 1 FROM event_types WHERE id = ? AND user_id = ?",
      [existingId, user.id],
    );
    if (owned.length === 0) return c.redirect("/event-types");
    etId = existingId;
    await db.query(
      `UPDATE event_types SET title = ?, description = ?, duration_min = ?, buffer_before_min = ?,
         buffer_after_min = ?, min_notice_hours = ?, max_per_day = ?, days_ahead = ?,
         slot_step_min = ?, is_active = ?
       WHERE id = ?`,
      [title, description, duration, bufBefore, bufAfter, minNotice, maxPerDay, daysAhead, step, isActive, etId],
    );
  }

  await db.query("DELETE FROM availability_rules WHERE event_type_id = ?", [etId]);
  if (endMin > startMin) {
    for (const w of weekdays) {
      await db.query(
        "INSERT INTO availability_rules (event_type_id, weekday, start_min, end_min) VALUES (?, ?, ?, ?)",
        [etId, w, startMin, endMin],
      );
    }
  }
  return c.redirect("/event-types");
}

hostRoutes.post("/event-types", (c) => saveEventType(c, null));

hostRoutes.get("/event-types/:id", async (c) => {
  const user = c.get("user");
  const db = dbStub(c.env);
  const ets = (await db.query(
    "SELECT * FROM event_types WHERE id = ? AND user_id = ?",
    [Number(c.req.param("id")), user.id],
  )) as unknown as EventTypeRow[];
  if (ets.length === 0) return c.redirect("/event-types");
  const rules = (await db.query(
    "SELECT * FROM availability_rules WHERE event_type_id = ?",
    [ets[0].id],
  )) as unknown as RuleRow[];
  return c.html(eventTypeFormPage({ et: ets[0], rules }));
});

hostRoutes.post("/event-types/:id", (c) =>
  saveEventType(c, Number(c.req.param("id"))),
);

hostRoutes.get("/event-types/:id/candidates", async (c) => {
  const user = c.get("user");
  const db = dbStub(c.env);
  const ets = (await db.query(
    "SELECT * FROM event_types WHERE id = ? AND user_id = ?",
    [Number(c.req.param("id")), user.id],
  )) as unknown as EventTypeRow[];
  if (ets.length === 0) return c.redirect("/event-types");
  const slots = await slotsForEventType(c.env, db, user, ets[0]);
  return c.html(
    candidatesPage({ et: ets[0], tz: user.timezone, slots: slots.slice(0, 10) }),
  );
});

/* ---------- 設定 ---------- */

hostRoutes.get("/settings", async (c) => {
  const user = c.get("user");
  const db = dbStub(c.env);
  try {
    const token = await getValidAccessToken(c.env, db, user);
    const calendars = await listCalendars(c.env, token);
    const busy = (await db.query(
      "SELECT calendar_id FROM busy_calendars WHERE user_id = ?",
      [user.id],
    )) as { calendar_id: string }[];
    return c.html(
      settingsPage({
        user,
        calendars,
        busyIds: new Set(busy.map((b) => b.calendar_id)),
        saved: c.req.query("saved") === "1",
      }),
    );
  } catch (e) {
    if (e instanceof GoogleApiError || e instanceof Error) {
      return c.html(
        messagePage(
          "カレンダーの取得に失敗しました",
          "Googleとの連携が切れている可能性があります。トップページからログインし直してください。",
        ),
        502,
      );
    }
    throw e;
  }
});

hostRoutes.post("/settings", async (c) => {
  const user = c.get("user");
  const db = dbStub(c.env);
  const fd = await c.req.raw.formData();

  const tz = String(fd.get("timezone") ?? "Asia/Tokyo").trim();
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: tz });
  } catch {
    return c.redirect("/settings");
  }
  const bookingCal = String(fd.get("booking_calendar_id") ?? "primary").slice(0, 300);
  await db.query(
    "UPDATE users SET timezone = ?, booking_calendar_id = ? WHERE id = ?",
    [tz, bookingCal, user.id],
  );

  await db.query("DELETE FROM busy_calendars WHERE user_id = ?", [user.id]);
  for (const cal of fd.getAll("busy_calendar").slice(0, 50)) {
    await db.query(
      "INSERT OR IGNORE INTO busy_calendars (user_id, calendar_id) VALUES (?, ?)",
      [user.id, String(cal).slice(0, 300)],
    );
  }
  return c.redirect("/settings?saved=1");
});
