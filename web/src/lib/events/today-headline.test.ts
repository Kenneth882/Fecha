import { describe, expect, it } from "vitest";

import type { components } from "@/lib/api/schema";

import { todayHeadline } from "./today-headline";

type TodayDetail = components["schemas"]["TodayDetail"];

function today(overrides: Partial<TodayDetail>): TodayDetail {
  return {
    today: "2026-11-20",
    plan_day: 4,
    plan_days: 15,
    days_until_event_day: 12,
    state: "active",
    current_plan_version: 1,
    tasks: [],
    ...overrides,
  };
}

describe("todayHeadline", () => {
  it("shows the demo account's Day 4 of 15 and its countdown", () => {
    expect(todayHeadline(today({}))).toEqual({
      title: "Day 4 of 15",
      countdown: "12 days until your Event Day",
      message: null,
    });
  });

  it("says tomorrow on the last Plan Day", () => {
    const headline = todayHeadline(today({ plan_day: 15, days_until_event_day: 1 }));
    expect(headline.title).toBe("Day 15 of 15");
    expect(headline.countdown).toBe("Your Event Day is tomorrow");
  });

  it("replaces the Tasks with a message on the Event Day", () => {
    const headline = todayHeadline(today({ state: "event_day", plan_day: null, days_until_event_day: 0 }));
    expect(headline).toEqual({
      title: "It's your Event Day",
      countdown: null,
      message: "No Tasks today: you've done the work. ¡Mucha suerte!",
    });
  });

  it("replaces the Tasks with a message for a Past Event", () => {
    const headline = todayHeadline(today({ state: "past", plan_day: null, days_until_event_day: 0 }));
    expect(headline).toEqual({
      title: "This Event is over",
      countdown: null,
      message: "Its Plan is finished. Set up your next Event to start a new one.",
    });
  });
});
