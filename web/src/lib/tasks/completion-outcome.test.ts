import { describe, expect, it } from "vitest";

import { completionOutcome } from "./completion-outcome";

describe("completionOutcome", () => {
  it("goes to Today once the Task is completed", () => {
    expect(completionOutcome(200, { task_id: "t1", status: "completed", items_introduced: 6 })).toEqual({
      kind: "today",
    });
  });

  it("says why when the Task can't be completed: Missed, or for a later Plan Day", () => {
    const message = "This Task was missed: its Plan Day has ended, so it can't be completed";
    const body = { error: { code: "task_missed", message, details: [], request_id: "req-1" } };
    expect(completionOutcome(409, body)).toEqual({ kind: "error", message });
  });

  it("says so when CramPlan can't be reached", () => {
    expect(completionOutcome(null, undefined)).toEqual({
      kind: "error",
      message: "CramPlan can't be reached. Check your connection.",
    });
  });
});
