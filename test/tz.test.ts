import { describe, expect, it } from "vitest";
import { dateKey, startOfDayZoned, tzOffsetMs, utcToZoned, zonedToUtc } from "../src/tz";

describe("tz", () => {
  it("utcToZoned converts to Asia/Tokyo", () => {
    // 2026-07-15T00:00:00Z = JST 9:00 (水曜)
    const ts = Date.UTC(2026, 6, 15, 0, 0);
    const p = utcToZoned(ts, "Asia/Tokyo");
    expect(p).toEqual({ year: 2026, month: 7, day: 15, hour: 9, minute: 0, weekday: 3 });
  });

  it("handles midnight (hour24 normalization)", () => {
    const ts = Date.UTC(2026, 6, 14, 15, 0); // JST 2026-07-15 00:00
    const p = utcToZoned(ts, "Asia/Tokyo");
    expect(p.hour).toBe(0);
    expect(p.day).toBe(15);
  });

  it("tzOffsetMs returns +9h for Tokyo", () => {
    expect(tzOffsetMs(Date.UTC(2026, 6, 15), "Asia/Tokyo")).toBe(9 * 3600_000);
  });

  it("zonedToUtc roundtrips", () => {
    const ts = zonedToUtc(2026, 7, 15, 9, 0, "Asia/Tokyo");
    expect(ts).toBe(Date.UTC(2026, 6, 15, 0, 0));
    const p = utcToZoned(ts, "Asia/Tokyo");
    expect([p.year, p.month, p.day, p.hour, p.minute]).toEqual([2026, 7, 15, 9, 0]);
  });

  it("zonedToUtc accepts minutes-of-day beyond 59", () => {
    // 10:30 を「0時から630分」として渡す
    expect(zonedToUtc(2026, 7, 15, 0, 630, "Asia/Tokyo")).toBe(
      zonedToUtc(2026, 7, 15, 10, 30, "Asia/Tokyo"),
    );
  });

  it("handles US DST transition", () => {
    // 2026-03-08 America/New_York: 2:00で夏時間へ
    const before = zonedToUtc(2026, 3, 8, 1, 0, "America/New_York");
    const after = zonedToUtc(2026, 3, 8, 3, 0, "America/New_York");
    expect(before).toBe(Date.UTC(2026, 2, 8, 6, 0)); // EST(-5)
    expect(after).toBe(Date.UTC(2026, 2, 8, 7, 0)); // EDT(-4)
  });

  it("startOfDayZoned / dateKey", () => {
    const ts = Date.UTC(2026, 6, 15, 3, 30); // JST 12:30
    expect(startOfDayZoned(ts, "Asia/Tokyo")).toBe(Date.UTC(2026, 6, 14, 15, 0));
    expect(dateKey(ts, "Asia/Tokyo")).toBe("2026-07-15");
  });
});
