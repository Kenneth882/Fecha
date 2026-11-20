"use client";

import { useRouter } from "next/navigation";
import { useReducer, useRef, useState } from "react";

import { createBrowserApiClient } from "@/lib/api/browser";
import {
  currentReview,
  gradeOutcome,
  nextReviewState,
  startReviewSession,
  type Grade,
  type ReviewItem,
  type ReviewSessionState,
} from "@/lib/reviews/review-session";

/** A Grade's POST gives up after this long, so the summary never waits forever. */
const SAVE_TIMEOUT_MS = 10_000;

/**
 * "Show translation" ignores taps this soon after a Grade: it takes the Grade buttons'
 * place, so a fast double-tap would otherwise reveal the next item unrecalled.
 */
const REVEAL_GUARD_MS = 400;

const GRADES: { grade: Grade; label: string; tone: string }[] = [
  { grade: "again", label: "Again", tone: "border-red-600/40 text-red-700 dark:text-red-400" },
  { grade: "hard", label: "Hard", tone: "border-amber-500/50 text-amber-800 dark:text-amber-300" },
  { grade: "good", label: "Good", tone: "border-green-600/40 text-green-800 dark:text-green-300" },
  { grade: "easy", label: "Easy", tone: "border-blue-600/40 text-blue-800 dark:text-blue-300" },
];

/**
 * One item at a time: the phrase, then its translation, then a Grade. A Grade moves on
 * straight away; its POST finishes in the background (a 409, already graded, is
 * skipped quietly). The summary waits for them all before going back to Today.
 */
export function ReviewSession({
  eventId,
  language,
  items,
}: {
  eventId: string;
  language: string;
  items: ReviewItem[];
}) {
  const [state, dispatch] = useReducer(nextReviewState, items, startReviewSession);
  const saves = useRef<Promise<void>[]>([]);
  const gradedAt = useRef(0);
  const review = currentReview(state);

  function submitGrade(item: ReviewItem, grade: Grade, at: number) {
    dispatch({ type: "grade", grade });
    gradedAt.current = at;
    const save = createBrowserApiClient()
      .POST("/api/v1/events/{event_id}/reviews", {
        params: { path: { event_id: eventId } },
        body: { vocab_item_id: item.vocab_item_id, grade },
        signal: AbortSignal.timeout(SAVE_TIMEOUT_MS),
      })
      .then(({ response }) => response.status)
      .catch(() => null)
      .then((status) => {
        if (gradeOutcome(status) === "not_saved") dispatch({ type: "notSaved" });
      });
    saves.current.push(save);
  }

  function reveal(at: number) {
    if (at - gradedAt.current < REVEAL_GUARD_MS) return;
    dispatch({ type: "reveal" });
  }

  if (!review) return <Summary state={state} saved={() => Promise.all(saves.current)} />;

  const { item, revealed } = review;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Review</h1>
        <span className="text-sm tabular-nums opacity-75" data-testid="review-progress">
          {state.index + 1} of {state.items.length}
        </span>
      </div>

      <section
        aria-live="polite"
        className="flex min-h-48 flex-col items-center justify-center gap-3 rounded-lg border border-current/15 px-4 py-8 text-center"
      >
        <p className="text-sm opacity-60">{item.scenario_title}</p>
        <p lang={language} className="text-2xl font-semibold" data-testid="review-phrase">
          {item.phrase}
        </p>
        {revealed && (
          <p className="text-lg opacity-80" data-testid="review-translation">
            {item.translation}
          </p>
        )}
      </section>

      {revealed ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="group" aria-label="How well did you recall it?">
          {GRADES.map(({ grade, label, tone }) => (
            <button
              key={grade}
              type="button"
              onClick={(event) => submitGrade(item, grade, event.timeStamp)}
              data-testid={`grade-${grade}`}
              className={`rounded-md border px-3 py-3 font-medium ${tone}`}
            >
              {label}
            </button>
          ))}
        </div>
      ) : (
        <button
          type="button"
          onClick={(event) => reveal(event.timeStamp)}
          data-testid="review-reveal"
          className="rounded-md bg-blue-700 px-4 py-3 font-medium text-white"
        >
          Show translation
        </button>
      )}
    </div>
  );
}

function Summary({ state, saved }: { state: ReviewSessionState; saved: () => Promise<unknown> }) {
  const [leaving, setLeaving] = useState(false);
  const router = useRouter();

  async function backToToday() {
    setLeaving(true);
    // Today's count is only right once every Grade has been saved (or given up on).
    await saved();
    router.replace("/today");
    router.refresh();
  }

  return (
    <div className="flex flex-col gap-6" data-testid="review-summary">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Reviews done</h1>
        <p className="opacity-80">
          You reviewed {state.items.length === 1 ? "1 phrase" : `${state.items.length} phrases`}.
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {GRADES.map(({ grade, label }) => (
          <div key={grade} className="flex flex-col items-center rounded-lg bg-current/5 px-3 py-3">
            <dt className="text-sm opacity-75">{label}</dt>
            <dd className="text-2xl font-semibold tabular-nums" data-testid={`summary-${grade}`}>
              {state.counts[grade]}
            </dd>
          </div>
        ))}
      </dl>
      {state.notSaved > 0 && (
        <p role="alert" className="rounded-md bg-amber-500/15 px-3 py-2 text-sm">
          {state.notSaved === 1 ? "1 Grade wasn't" : `${state.notSaved} Grades weren't`} saved, so{" "}
          {state.notSaved === 1 ? "that phrase stays" : "those phrases stay"} in your Review Queue.
        </p>
      )}
      <button
        type="button"
        onClick={backToToday}
        disabled={leaving}
        className="rounded-md bg-blue-700 px-4 py-3 font-medium text-white disabled:opacity-60"
      >
        Back to Today
      </button>
    </div>
  );
}
