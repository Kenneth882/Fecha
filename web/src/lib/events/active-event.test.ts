import { describe, expect, it } from "vitest";

import type { components } from "@/lib/api/schema";

import { activeEvent } from "./active-event";

type EventSummary = components["schemas"]["EventSummary"];

function event(id: string, state: EventSummary["state"]): EventSummary {
  return {
    id,
    type: "interview",
    target_language: "es",
    event_day: "2026-12-02",
    abandoned_at: null,
    created_at: "2026-11-17T12:00:00Z",
    state,
    days_until_event_day: state === "past" ? 0 : 12,
  };
}

describe("activeEvent", () => {
  it("is null for a new User with no Events, who goes to onboarding", () => {
    expect(activeEvent([])).toBeNull();
  });

  it("is null when every Event is a Past Event", () => {
    expect(activeEvent([event("b", "past"), event("a", "past")])).toBeNull();
  });

  it("is the active Event among Past ones", () => {
    expect(activeEvent([event("c", "active"), event("b", "past")])?.id).toBe("c");
  });

  it("is the Event whose Event Day is today: it's still the Active Event", () => {
    expect(activeEvent([event("b", "event_day"), event("a", "past")])?.id).toBe("b");
  });
});
