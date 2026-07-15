import type { Env } from "./env";
import type { AppDB } from "./db";
import type { EventTypeRow, RuleRow, UserRow } from "./types";
import { computeSlots, type BusyInterval, type Slot } from "./slots";
import { freeBusyQuery, getValidAccessToken } from "./google";

const DAY_MS = 24 * 60 * 60 * 1000;

/** イベントタイプの空き枠を計算する(Google freebusy + 自前DBの予約を考慮) */
export async function slotsForEventType(
  env: Env,
  db: DurableObjectStub<AppDB>,
  user: UserRow,
  et: EventTypeRow,
): Promise<Slot[]> {
  const now = Date.now();
  const rangeStart = now;
  const rangeEnd = now + et.days_ahead * DAY_MS;

  const rules = (await db.query(
    "SELECT * FROM availability_rules WHERE event_type_id = ?",
    [et.id],
  )) as unknown as RuleRow[];
  if (rules.length === 0) return [];

  const busyCals = (await db.query(
    "SELECT calendar_id FROM busy_calendars WHERE user_id = ?",
    [user.id],
  )) as { calendar_id: string }[];

  const token = await getValidAccessToken(env, db, user);
  const busy: BusyInterval[] = await freeBusyQuery(
    env,
    token,
    busyCals.map((c) => c.calendar_id),
    rangeStart,
    rangeEnd,
  );

  // カレンダー未反映の予約(処理中含む)もブロック対象にする(このホストの分のみ)
  const dbBusy = (await db.query(
    `SELECT b.start_ts, b.end_ts FROM bookings b
     JOIN event_types et ON et.id = b.event_type_id
     WHERE et.user_id = ? AND b.status IN ('pending', 'confirmed')
       AND b.start_ts < ? AND b.end_ts > ?`,
    [user.id, rangeEnd, rangeStart],
  )) as unknown as { start_ts: number; end_ts: number }[];
  for (const b of dbBusy) busy.push({ start: b.start_ts, end: b.end_ts });

  const perDay = (await db.query(
    `SELECT host_date, COUNT(*) AS c FROM bookings
     WHERE status IN ('pending', 'confirmed') AND event_type_id = ?
     GROUP BY host_date`,
    [et.id],
  )) as { host_date: string; c: number }[];
  const bookedPerDay: Record<string, number> = {};
  for (const r of perDay) bookedPerDay[r.host_date] = r.c;

  return computeSlots({
    now,
    hostTz: user.timezone,
    durationMin: et.duration_min,
    bufferBeforeMin: et.buffer_before_min,
    bufferAfterMin: et.buffer_after_min,
    minNoticeMin: et.min_notice_hours * 60,
    maxPerDay: et.max_per_day,
    stepMin: et.slot_step_min,
    rangeStart,
    rangeEnd,
    rules: rules.map((r) => ({
      weekday: r.weekday,
      startMin: r.start_min,
      endMin: r.end_min,
    })),
    busy,
    bookedPerDay,
  });
}
