import { utcToZoned } from "./tz";

export const WEEKDAY_JP = ["日", "月", "火", "水", "木", "金", "土"];

function two(n: number): string {
  return String(n).padStart(2, "0");
}

/** 例: "7/16(木) 10:00" */
export function fmtDateTime(ts: number, tz: string): string {
  const p = utcToZoned(ts, tz);
  return `${p.month}/${p.day}(${WEEKDAY_JP[p.weekday]}) ${p.hour}:${two(p.minute)}`;
}

/** 例: "7/16(木) 10:00〜10:30" */
export function fmtRange(start: number, end: number, tz: string): string {
  const e = utcToZoned(end, tz);
  return `${fmtDateTime(start, tz)}〜${e.hour}:${two(e.minute)}`;
}

/** 分数 → "HH:MM" (フォーム値用) */
export function minToHHMM(min: number): string {
  return `${two(Math.floor(min / 60))}:${two(min % 60)}`;
}

/** "HH:MM" → 分数。不正値は null */
export function hhmmToMin(v: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(v.trim());
  if (!m) return null;
  const min = Number(m[1]) * 60 + Number(m[2]);
  return min >= 0 && min <= 24 * 60 ? min : null;
}
