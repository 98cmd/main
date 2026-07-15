import { startOfDayZoned, utcToZoned, zonedToUtc, dateKey } from "./tz";

export interface BusyInterval {
  start: number; // UTC ms
  end: number;
}

export interface AvailabilityRule {
  weekday: number; // 0=日 ... 6=土 (ホストTZ基準)
  startMin: number; // その日の0:00からの分数
  endMin: number;
}

export interface SlotParams {
  now: number;
  hostTz: string;
  durationMin: number;
  bufferBeforeMin: number;
  bufferAfterMin: number;
  minNoticeMin: number;
  maxPerDay: number | null;
  stepMin: number;
  /** 提示対象のUTC範囲 */
  rangeStart: number;
  rangeEnd: number;
  rules: AvailabilityRule[];
  busy: BusyInterval[];
  /** ホストTZの日付キー("YYYY-MM-DD") → その日の既存予約数 */
  bookedPerDay: Record<string, number>;
}

export interface Slot {
  start: number;
  end: number;
}

export function mergeBusy(intervals: BusyInterval[]): BusyInterval[] {
  const sorted = intervals
    .filter((i) => i.end > i.start)
    .slice()
    .sort((a, b) => a.start - b.start);
  const merged: BusyInterval[] = [];
  for (const cur of sorted) {
    const last = merged[merged.length - 1];
    if (last && cur.start <= last.end) {
      last.end = Math.max(last.end, cur.end);
    } else {
      merged.push({ ...cur });
    }
  }
  return merged;
}

function overlapsAny(merged: BusyInterval[], start: number, end: number): boolean {
  // merged はソート済み。二分探索でもよいが件数は少ないので線形で十分
  for (const b of merged) {
    if (b.start >= end) break;
    if (b.end > start) return true;
  }
  return false;
}

/** 空き枠を計算する(純関数)。返り値はUTC msの開始/終了ペア、開始時刻昇順 */
export function computeSlots(p: SlotParams): Slot[] {
  const merged = mergeBusy(p.busy);
  const earliest = Math.max(p.rangeStart, p.now + p.minNoticeMin * 60_000);
  const out: Slot[] = [];

  let dayStart = startOfDayZoned(Math.max(p.rangeStart, p.now), p.hostTz);
  // 安全弁: 範囲が異常に広くても1年分で打ち切る
  for (let i = 0; i < 366 && dayStart < p.rangeEnd; i++) {
    const d = utcToZoned(dayStart, p.hostTz);
    const key = dateKey(dayStart, p.hostTz);
    const alreadyBooked = p.bookedPerDay[key] ?? 0;
    const capReached = p.maxPerDay != null && alreadyBooked >= p.maxPerDay;

    if (!capReached) {
      for (const rule of p.rules) {
        if (rule.weekday !== d.weekday) continue;
        for (
          let t = rule.startMin;
          t + p.durationMin <= rule.endMin;
          t += p.stepMin
        ) {
          const start = zonedToUtc(d.year, d.month, d.day, 0, t, p.hostTz);
          const end = start + p.durationMin * 60_000;
          if (start < earliest || end > p.rangeEnd) continue;
          const guardStart = start - p.bufferBeforeMin * 60_000;
          const guardEnd = end + p.bufferAfterMin * 60_000;
          if (overlapsAny(merged, guardStart, guardEnd)) continue;
          out.push({ start, end });
        }
      }
    }
    dayStart = zonedToUtc(d.year, d.month, d.day + 1, 0, 0, p.hostTz);
  }

  out.sort((a, b) => a.start - b.start);
  // 複数ルールの重複窓で同一枠が二重に出ないよう除去
  return out.filter((s, i) => i === 0 || s.start !== out[i - 1].start);
}
