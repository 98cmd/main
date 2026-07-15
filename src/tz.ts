/**
 * タイムゾーン変換ユーティリティ。
 * Workers で利用できる Intl API のみで実装(外部ライブラリ不使用)。
 */

export interface ZonedParts {
  year: number;
  month: number; // 1-12
  day: number;
  hour: number;
  minute: number;
  weekday: number; // 0=日 ... 6=土
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const dtfCache = new Map<string, Intl.DateTimeFormat>();

function formatter(tz: string): Intl.DateTimeFormat {
  let dtf = dtfCache.get(tz);
  if (!dtf) {
    dtf = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      weekday: "short",
      hour12: false,
    });
    dtfCache.set(tz, dtf);
  }
  return dtf;
}

/** UTCタイムスタンプ(ms)を、指定タイムゾーンの日時パーツへ変換 */
export function utcToZoned(ts: number, tz: string): ZonedParts {
  const parts: Record<string, string> = {};
  for (const p of formatter(tz).formatToParts(new Date(ts))) {
    parts[p.type] = p.value;
  }
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    // Intl は 0時を "24" と返す実装があるため正規化
    hour: parts.hour === "24" ? 0 : Number(parts.hour),
    minute: Number(parts.minute),
    weekday: WEEKDAYS.indexOf(parts.weekday),
  };
}

/** 指定タイムゾーンのUTCオフセット(ms)。ts はUTCタイムスタンプ。分精度(実在オフセットは15分単位) */
export function tzOffsetMs(ts: number, tz: string): number {
  const p = utcToZoned(ts, tz);
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute);
  const tsMinute = Math.floor(ts / 60_000) * 60_000;
  return asUtc - tsMinute;
}

/**
 * 指定タイムゾーンのローカル日時 → UTCタイムスタンプ(ms)。
 * minute は 0-59 に限らず「その日の 0:00 からの分数」でもよい(Date.UTC が繰り上げる)。
 */
export function zonedToUtc(
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  tz: string,
): number {
  const naive = Date.UTC(year, month - 1, day, hour, minute);
  // オフセットを2回適用してDST境界を補正
  let ts = naive - tzOffsetMs(naive, tz);
  ts = naive - tzOffsetMs(ts, tz);
  return ts;
}

/** UTCタイムスタンプ ts を含む、指定タイムゾーンの「その日の0:00」のUTCタイムスタンプ */
export function startOfDayZoned(ts: number, tz: string): number {
  const p = utcToZoned(ts, tz);
  return zonedToUtc(p.year, p.month, p.day, 0, 0, tz);
}

/** "YYYY-MM-DD" (指定タイムゾーンでの日付キー) */
export function dateKey(ts: number, tz: string): string {
  const p = utcToZoned(ts, tz);
  return `${p.year}-${String(p.month).padStart(2, "0")}-${String(p.day).padStart(2, "0")}`;
}
