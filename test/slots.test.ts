import { describe, expect, it } from "vitest";
import { computeSlots, mergeBusy, type SlotParams } from "../src/slots";
import { zonedToUtc } from "../src/tz";

const TZ = "Asia/Tokyo";
// 2026-07-15(水) 12:00 JST
const NOW = zonedToUtc(2026, 7, 15, 12, 0, TZ);
const DAY = 24 * 3600_000;

function params(over: Partial<SlotParams> = {}): SlotParams {
  return {
    now: NOW,
    hostTz: TZ,
    durationMin: 30,
    bufferBeforeMin: 0,
    bufferAfterMin: 0,
    minNoticeMin: 0,
    maxPerDay: null,
    stepMin: 30,
    rangeStart: NOW,
    rangeEnd: NOW + 8 * DAY,
    rules: [{ weekday: 3, startMin: 600, endMin: 720 }], // 水 10:00-12:00
    busy: [],
    bookedPerDay: {},
    ...over,
  };
}

describe("computeSlots", () => {
  it("generates slots only in future windows", () => {
    const slots = computeSlots(params());
    // 今日(7/15水)の10:00-12:00枠は now=12:00 より前なので出ない。翌週水曜の4枠のみ
    expect(slots).toHaveLength(4);
    expect(slots[0].start).toBe(zonedToUtc(2026, 7, 22, 10, 0, TZ));
    expect(slots[3].start).toBe(zonedToUtc(2026, 7, 22, 11, 30, TZ));
    expect(slots[0].end - slots[0].start).toBe(30 * 60_000);
  });

  it("respects min notice", () => {
    // 7日以上先しか受け付けない → 7/22 10:00 の枠は 12:00 JST起点で7日後=7/22 12:00 より前なので除外
    const slots = computeSlots(params({ minNoticeMin: 7 * 24 * 60 }));
    expect(slots).toHaveLength(0);
  });

  it("excludes busy intervals with buffers", () => {
    const busyStart = zonedToUtc(2026, 7, 22, 10, 0, TZ);
    const slots = computeSlots(
      params({
        busy: [{ start: busyStart, end: busyStart + 30 * 60_000 }],
        bufferBeforeMin: 15,
      }),
    );
    // 10:00枠は重複、10:30枠は前バッファ(10:15〜)が10:00-10:30のbusyに当たる
    expect(slots.map((s) => s.start)).toEqual([
      zonedToUtc(2026, 7, 22, 11, 0, TZ),
      zonedToUtc(2026, 7, 22, 11, 30, TZ),
    ]);
  });

  it("respects maxPerDay using host-date counts", () => {
    const slots = computeSlots(
      params({ maxPerDay: 1, bookedPerDay: { "2026-07-22": 1 } }),
    );
    expect(slots).toHaveLength(0);
  });

  it("dedupes overlapping rules", () => {
    const slots = computeSlots(
      params({
        rules: [
          { weekday: 3, startMin: 600, endMin: 720 },
          { weekday: 3, startMin: 600, endMin: 660 },
        ],
      }),
    );
    expect(slots).toHaveLength(4);
  });

  it("slot must fit inside the window", () => {
    const slots = computeSlots(
      params({ durationMin: 90, rules: [{ weekday: 3, startMin: 600, endMin: 660 }] }),
    );
    expect(slots).toHaveLength(0);
  });
});

describe("mergeBusy", () => {
  it("merges overlapping and adjacent intervals", () => {
    expect(
      mergeBusy([
        { start: 10, end: 20 },
        { start: 15, end: 30 },
        { start: 30, end: 40 },
        { start: 50, end: 60 },
        { start: 5, end: 4 }, // 不正(無視される)
      ]),
    ).toEqual([
      { start: 10, end: 40 },
      { start: 50, end: 60 },
    ]);
  });
});
