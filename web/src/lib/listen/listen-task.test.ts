import { describe, expect, it } from "vitest";

import type { components } from "@/lib/api/schema";

import { answerOutcome, nextListenState, readOnlyMessage, startListen, type ListenState } from "./listen-task";

type ListenTask = components["schemas"]["ListenTask"];

const OPTIONS = ["Lucía", "Marcos", "Nobody"];

function listenTask(overrides: Partial<ListenTask> = {}): ListenTask {
  return {
    task_id: "t1",
    status: "pending",
    answerable: true,
    speakers: ["Lucía", "Marcos"],
    lines: [{ speaker: "Lucía", text: "Siéntese, por favor." }],
    questions: [1, 2, 3].map((number) => ({ number, prompt: `Question ${number}?`, options: OPTIONS, answer: null })),
    ...overrides,
  };
}

function result(question: number, choice: number, correctOption: number, status: "pending" | "completed" = "pending") {
  return { task_id: "t1", question, choice, correct: choice === correctOption, correct_option: correctOption, status };
}

describe("startListen", () => {
  it("opens every unanswered question on an answerable Task", () => {
    const state = startListen(listenTask());
    expect(state.questions).toEqual({ 1: { kind: "open" }, 2: { kind: "open" }, 3: { kind: "open" } });
    expect(state.completed).toBe(false);
  });

  it("shows the answers already given when the Task is reopened", () => {
    const task = listenTask();
    task.questions[0] = { ...task.questions[0], answer: { choice: 2, correct: false, correct_option: 1 } };

    expect(startListen(task).questions[1]).toEqual({ kind: "answered", choice: 2, correct: false, correctOption: 1 });
  });

  it("locks every unanswered question on a read-only Task", () => {
    const state = startListen(listenTask({ status: "missed", answerable: false }));
    expect(Object.values(state.questions)).toEqual([{ kind: "locked" }, { kind: "locked" }, { kind: "locked" }]);
  });

  it("knows a completed Task is complete", () => {
    expect(startListen(listenTask({ status: "completed", answerable: false })).completed).toBe(true);
  });
});

describe("nextListenState", () => {
  const start = (): ListenState => startListen(listenTask());

  it("sends a choice for an open question, and only once: a second tap is ignored", () => {
    const sending = nextListenState(start(), { type: "choose", question: 1, choice: 2 });
    expect(sending.questions[1]).toEqual({ kind: "sending", choice: 2 });

    expect(nextListenState(sending, { type: "choose", question: 1, choice: 3 })).toBe(sending);
  });

  it("ignores a choice for a question that's already answered or locked", () => {
    const answered = nextListenState(start(), { type: "answered", result: result(1, 1, 1) });
    expect(nextListenState(answered, { type: "choose", question: 1, choice: 2 })).toBe(answered);

    const readOnly = startListen(listenTask({ answerable: false }));
    expect(nextListenState(readOnly, { type: "choose", question: 1, choice: 2 })).toBe(readOnly);
  });

  it("reveals whether the answer was right and which option was correct", () => {
    const sending = nextListenState(start(), { type: "choose", question: 2, choice: 3 });

    const answered = nextListenState(sending, { type: "answered", result: result(2, 3, 1) });

    expect(answered.questions[2]).toEqual({ kind: "answered", choice: 3, correct: false, correctOption: 1 });
    expect(answered.completed).toBe(false);
  });

  it("completes the Task when the third answer says so", () => {
    let state = start();
    for (const question of [1, 2, 3]) {
      state = nextListenState(state, { type: "choose", question, choice: 1 });
      state = nextListenState(state, {
        type: "answered",
        result: result(question, 1, 1, question === 3 ? "completed" : "pending"),
      });
    }
    expect(state.completed).toBe(true);
  });

  it("reopens a question whose answer wasn't saved, with the reason", () => {
    const sending = nextListenState(start(), { type: "choose", question: 1, choice: 2 });

    const failed = nextListenState(sending, { type: "failed", question: 1, message: "Try again." });

    expect(failed.questions[1]).toEqual({ kind: "open" });
    expect(failed.error).toBe("Try again.");
    expect(nextListenState(failed, { type: "choose", question: 1, choice: 2 }).error).toBeNull();
  });
});

describe("nextListenState after a lost reply", () => {
  it("syncs from the Task as reloaded: a saved answer is shown and the Task completes", () => {
    const sending = nextListenState(startListen(listenTask()), { type: "choose", question: 3, choice: 2 });
    const failed = nextListenState(sending, { type: "failed", question: 3, message: "Lost." });
    const reloaded = listenTask({ status: "completed", answerable: false });
    reloaded.questions = reloaded.questions.map((q) => ({ ...q, answer: { choice: 2, correct: true, correct_option: 2 } }));

    const synced = nextListenState(failed, { type: "sync", task: reloaded });

    expect(synced.questions[3]).toEqual({ kind: "answered", choice: 2, correct: true, correctOption: 2 });
    expect(synced.completed).toBe(true);
    expect(synced.error).toBeNull();
  });
});

describe("answerOutcome", () => {
  it("passes on the saved answer", () => {
    const saved = result(1, 2, 2);
    expect(answerOutcome({ data: saved })).toEqual({ kind: "answered", result: saved });
  });

  it("spots an answer that was already saved, whose reply was lost", () => {
    const body = { error: { code: "question_already_answered", message: "Already.", details: [], request_id: "r" } };
    expect(answerOutcome({ error: body })).toEqual({ kind: "alreadyAnswered" });
  });

  it("says why an answer was refused, in FastAPI's words", () => {
    const message = "This Task was missed: its Plan Day has ended, so it can't be completed";
    const body = { error: { code: "task_missed", message, details: [], request_id: "req-1" } };
    expect(answerOutcome({ error: body })).toEqual({ kind: "error", message });
  });

  it("says so when CramPlan can't be reached", () => {
    expect(answerOutcome(null)).toEqual({
      kind: "error",
      message: "CramPlan can't be reached. Check your connection.",
    });
  });
});

describe("readOnlyMessage", () => {
  it("has nothing to say about a Task that can be answered", () => {
    expect(readOnlyMessage(listenTask(), { pastEvent: false })).toBeNull();
  });

  it("explains a Missed Task can't be answered any more", () => {
    expect(readOnlyMessage(listenTask({ status: "missed", answerable: false }), { pastEvent: false })).toBe(
      "This Task was missed: its Plan Day has passed, so its questions can't be answered any more.",
    );
  });

  it("explains a Task of another Plan Day can be answered on that day", () => {
    expect(readOnlyMessage(listenTask({ status: "pending", answerable: false }), { pastEvent: false })).toBe(
      "This Task isn't one of today's. You can answer its questions on its Plan Day.",
    );
  });

  it("explains a Past Event's Task can't be answered any more, whatever its status", () => {
    for (const status of ["pending", "missed"] as const) {
      expect(readOnlyMessage(listenTask({ status, answerable: false }), { pastEvent: true })).toBe(
        "This Task is part of a past Event, so its questions can't be answered any more.",
      );
    }
  });

  it("leaves a completed Task to the Done panel", () => {
    expect(readOnlyMessage(listenTask({ status: "completed", answerable: false }), { pastEvent: true })).toBeNull();
  });
});
