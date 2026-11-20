import type { components } from "@/lib/api/schema";

export type ReviewItem = Pick<
  components["schemas"]["DueReview"],
  "vocab_item_id" | "phrase" | "translation" | "scenario_title"
>;

export type Grade = components["schemas"]["Grade"];

/**
 * A Review session over the Review Queue as it was when the session began: one item
 * at a time, phrase first, then its translation, then a Grade.
 */
export type ReviewSessionState = {
  items: ReviewItem[];
  index: number;
  revealed: boolean;
  /** How many of each Grade the User gave, for the summary. */
  counts: Record<Grade, number>;
  /** Grades whose POST failed: those items stay in the Review Queue. */
  notSaved: number;
};

export type ReviewAction =
  | { type: "reveal" }
  | { type: "grade"; grade: Grade }
  /** A Grade's POST failed. It arrives after the session has moved on. */
  | { type: "notSaved" };

export function startReviewSession(items: ReviewItem[]): ReviewSessionState {
  return { items, index: 0, revealed: false, counts: { again: 0, hard: 0, good: 0, easy: 0 }, notSaved: 0 };
}

/** The Review on screen, or null once every item is graded (the summary). */
export function currentReview(state: ReviewSessionState): { item: ReviewItem; revealed: boolean } | null {
  const item = state.items[state.index];
  return item ? { item, revealed: state.revealed } : null;
}

/** Grading moves straight on: the session never waits for FastAPI's answer. */
export function nextReviewState(state: ReviewSessionState, action: ReviewAction): ReviewSessionState {
  switch (action.type) {
    case "reveal":
      return { ...state, revealed: true };
    case "grade":
      return {
        ...state,
        index: state.index + 1,
        revealed: false,
        counts: { ...state.counts, [action.grade]: state.counts[action.grade] + 1 },
      };
    case "notSaved":
      return { ...state, notSaved: state.notSaved + 1 };
  }
}

export type GradeOutcome = "saved" | "skipped" | "not_saved";

/**
 * What POST /reviews's response (its status, `null` if it never arrived) means for a
 * Grade the session has already moved on from. A 409 means the item isn't due any
 * more (graded in another tab, or it's the Event Day), so it's skipped quietly.
 */
export function gradeOutcome(status: number | null): GradeOutcome {
  if (status === null) return "not_saved";
  if (status >= 200 && status < 300) return "saved";
  return status === 409 ? "skipped" : "not_saved";
}
