import { describe, expect, it } from "vitest";

import { onboardingOutcome } from "./onboarding-outcome";

function errorBody(code: string, message: string, details: { field: string | null; code: string; message: string }[] = []) {
  return { error: { code, message, details, request_id: "req-1" } };
}

describe("onboardingOutcome", () => {
  it("goes to Today once the Event is created", () => {
    expect(onboardingOutcome(201, { id: "e1" })).toEqual({ kind: "today" });
  });

  it("goes to Today when the User already has an Active Event (409)", () => {
    const body = errorBody("active_event_exists", "You already have an Active Event");
    expect(onboardingOutcome(409, body)).toEqual({ kind: "today" });
  });

  it("puts an out-of-range Event Day on the Event Day field", () => {
    const message = "The Event Day must be 3 to 60 days after your local today";
    const body = errorBody("event_day_out_of_range", message);
    expect(onboardingOutcome(422, body)).toEqual({
      kind: "errors",
      errors: { form: null, fields: { event_day: message } },
    });
  });

  it("shows FastAPI's field errors inline, such as goals that are too long", () => {
    const body = errorBody("validation_error", "The request is invalid", [
      { field: "goals", code: "string_too_long", message: "String should have at most 500 characters" },
    ]);
    expect(onboardingOutcome(422, body)).toEqual({
      kind: "errors",
      errors: { form: null, fields: { goals: "String should have at most 500 characters" } },
    });
  });

  it("says so when CramPlan can't be reached", () => {
    expect(onboardingOutcome(null, undefined)).toEqual({
      kind: "errors",
      errors: { form: "CramPlan can't be reached. Check your connection.", fields: {} },
    });
  });
});
