import { describe, expect, it } from "vitest";

import { currentReview, gradeOutcome, nextReviewState, startReviewSession } from "./review-session";

const hola = { vocab_item_id: "v1", phrase: "hola", translation: "hello", scenario_title: "Greetings" };
const gracias = { vocab_item_id: "v2", phrase: "gracias", translation: "thank you", scenario_title: "Greetings" };
const adios = { vocab_item_id: "v3", phrase: "adiós", translation: "goodbye", scenario_title: "Greetings" };

describe("nextReviewState", () => {
  it("starts on the first phrase, with its translation hidden", () => {
    const state = startReviewSession([hola]);
    expect(currentReview(state)).toEqual({ item: hola, revealed: false });
  });

  it("reveals the translation", () => {
    const state = nextReviewState(startReviewSession([hola]), { type: "reveal" });
    expect(currentReview(state)).toEqual({ item: hola, revealed: true });
  });

  it("moves straight on to the next phrase once one is graded, hidden again", () => {
    let state = startReviewSession([hola, gracias]);
    state = nextReviewState(state, { type: "reveal" });
    state = nextReviewState(state, { type: "grade", grade: "good" });
    expect(currentReview(state)).toEqual({ item: gracias, revealed: false });
  });

  it("ends with how many of each Grade were given", () => {
    let state = startReviewSession([hola, gracias, adios]);
    for (const grade of ["again", "good", "good"] as const) {
      state = nextReviewState(state, { type: "reveal" });
      state = nextReviewState(state, { type: "grade", grade });
    }
    expect(currentReview(state)).toBeNull();
    expect(state.counts).toEqual({ again: 1, hard: 0, good: 2, easy: 0 });
  });

  it("counts the Grades that weren't saved, whenever their responses arrive", () => {
    let state = startReviewSession([hola, gracias]);
    state = nextReviewState(state, { type: "grade", grade: "good" });
    state = nextReviewState(state, { type: "grade", grade: "easy" });
    state = nextReviewState(state, { type: "notSaved" });
    expect(state.notSaved).toBe(1);
    expect(state.counts).toEqual({ again: 0, hard: 0, good: 1, easy: 1 });
  });
});

describe("gradeOutcome", () => {
  it("is saved when FastAPI accepts the Grade", () => {
    expect(gradeOutcome(200)).toBe("saved");
  });

  it("skips quietly when the item isn't due any more (409: already graded)", () => {
    expect(gradeOutcome(409)).toBe("skipped");
  });

  it("isn't saved when FastAPI fails or can't be reached", () => {
    expect(gradeOutcome(502)).toBe("not_saved");
    expect(gradeOutcome(null)).toBe("not_saved");
  });
});
