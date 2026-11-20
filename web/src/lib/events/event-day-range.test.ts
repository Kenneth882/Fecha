import { describe, expect, it } from "vitest";

import { eventDayRange } from "./event-day-range";

describe("eventDayRange", () => {
  it("allows an Event Day 3 to 60 days after the User's local today", () => {
    const range = eventDayRange(new Date("2026-11-20T12:00:00Z"), "Europe/Madrid");
    expect(range).toEqual({ min: "2026-11-23", max: "2027-01-19" });
  });

  it("counts from the User's local today, not UTC's", () => {
    // 23:30 UTC on the 20th is already the 21st in Madrid and still the 20th in LA.
    const now = new Date("2026-11-20T23:30:00Z");
    expect(eventDayRange(now, "Europe/Madrid").min).toBe("2026-11-24");
    expect(eventDayRange(now, "America/Los_Angeles").min).toBe("2026-11-23");
  });

  it("crosses month ends and leap days", () => {
    const range = eventDayRange(new Date("2028-02-27T12:00:00Z"), "UTC");
    expect(range.min).toBe("2028-03-01");
    expect(range.max).toBe("2028-04-27");
  });
});
