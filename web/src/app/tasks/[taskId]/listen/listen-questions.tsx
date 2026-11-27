"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { FormError } from "@/components/auth-form";
import { createBrowserApiClient } from "@/lib/api/browser";
import type { components } from "@/lib/api/schema";
import {
  answerOutcome,
  nextListenState,
  readOnlyMessage,
  startListen,
  type ListenAction,
  type QuestionState,
} from "@/lib/listen/listen-task";

type ListenTask = components["schemas"]["ListenTask"];
type ListenQuestion = components["schemas"]["ListenQuestion"];

/** An answer's POST gives up after this long, so a question never stays Sending. */
const SAVE_TIMEOUT_MS = 10_000;

/**
 * The three Comprehension Questions. Tapping an option sends it as the final answer;
 * FastAPI's reply reveals right or wrong and the correct option. The third answer
 * completes the Task, and Today is refreshed to show it.
 */
export function ListenQuestions({ task, pastEvent }: { task: ListenTask; pastEvent: boolean }) {
  const [state, setState] = useState(() => startListen(task));
  // The latest state, read synchronously: two taps in one tick both see the first as
  // Sending, so only one answer is sent.
  const latest = useRef(state);
  const router = useRouter();

  function apply(action: ListenAction): boolean {
    const next = nextListenState(latest.current, action);
    if (next === latest.current) return false;
    latest.current = next;
    setState(next);
    return true;
  }

  async function choose(question: number, choice: number) {
    if (!apply({ type: "choose", question, choice })) return;
    const reply = await createBrowserApiClient()
      .POST("/api/v1/tasks/{task_id}/answers", {
        params: { path: { task_id: task.task_id } },
        body: { question, choice },
        signal: AbortSignal.timeout(SAVE_TIMEOUT_MS),
      })
      .catch(() => null);
    const outcome = answerOutcome(reply);
    if (outcome.kind === "alreadyAnswered") {
      // An earlier reply was lost after FastAPI saved the answer: show what it saved.
      const reloaded = await createBrowserApiClient()
        .GET("/api/v1/tasks/{task_id}/listen", { params: { path: { task_id: task.task_id } } })
        .catch(() => null);
      if (reloaded?.data) {
        apply({ type: "sync", task: reloaded.data });
        if (reloaded.data.status === "completed") router.refresh();
        return;
      }
      apply({ type: "failed", question, message: "CramPlan can't be reached. Check your connection." });
      return;
    }
    if (outcome.kind === "error") {
      apply({ type: "failed", question, message: outcome.message });
      return;
    }
    apply({ type: "answered", result: outcome.result });
    // Today and the Plan show the Task's status, so they must not come from the cache.
    if (outcome.result.status === "completed") router.refresh();
  }

  const readOnly = readOnlyMessage(task, { pastEvent });
  return (
    <section aria-labelledby="questions-heading" className="flex flex-col gap-4">
      <h2 id="questions-heading" className="text-sm font-medium opacity-75">
        Questions
      </h2>
      <ol className="flex flex-col gap-4">
        {task.questions.map(({ number, prompt, options }) => (
          <li key={number}>
            <Question
              number={number}
              prompt={prompt}
              options={options}
              state={state.questions[number] ?? { kind: "locked" }}
              onChoose={(choice) => choose(number, choice)}
            />
          </li>
        ))}
      </ol>

      <FormError message={state.error} />

      {state.completed ? (
        <div className="flex flex-col gap-3 rounded-lg bg-green-600/10 px-4 py-4" role="status" data-testid="listen-complete">
          <p className="font-medium">Done: you&apos;ve answered all three questions.</p>
          <Link href="/today" className="self-start rounded-md bg-blue-700 px-4 py-3 font-medium text-white">
            Back to Today
          </Link>
        </div>
      ) : (
        readOnly && (
          <p className="rounded-md bg-current/5 px-3 py-2 text-sm" data-testid="task-readonly">
            {readOnly}
          </p>
        )
      )}
    </section>
  );
}

function Question({
  number,
  prompt,
  options,
  state,
  onChoose,
}: Pick<ListenQuestion, "number" | "prompt" | "options"> & {
  state: QuestionState;
  onChoose: (choice: number) => void;
}) {
  const promptId = `question-${number}`;
  const answered = state.kind === "answered" ? state : null;
  return (
    <div className="flex flex-col gap-2" data-testid={`question-${number}`}>
      <p id={promptId} className="font-medium">
        {number}. {prompt}
      </p>
      <div role="group" aria-labelledby={promptId} className="flex flex-col gap-2">
        {options.map((option, index) => {
          const choice = index + 1;
          const chosen = (state.kind === "sending" || state.kind === "answered") && state.choice === choice;
          const isCorrect = answered?.correctOption === choice;
          const tone = answered
            ? isCorrect
              ? "border-green-600 bg-green-600/10"
              : chosen
                ? "border-red-600 bg-red-600/10"
                : "border-current/15 opacity-60"
            : chosen
              ? "border-blue-600 bg-blue-600/10"
              : "border-current/15 hover:border-blue-600";
          return (
            <button
              key={choice}
              type="button"
              disabled={state.kind !== "open"}
              aria-pressed={chosen}
              onClick={() => onChoose(choice)}
              data-testid={`option-${number}-${choice}`}
              className={`flex items-center justify-between gap-3 rounded-md border px-4 py-3 text-left disabled:cursor-default ${tone}`}
            >
              <span>{option}</span>
              {answered && isCorrect && <span className="shrink-0 text-sm font-medium">Correct answer</span>}
              {answered && chosen && !isCorrect && <span className="shrink-0 text-sm font-medium">Your answer</span>}
              {state.kind === "sending" && chosen && <span className="shrink-0 text-sm opacity-75">Saving…</span>}
            </button>
          );
        })}
      </div>
      <p aria-live="polite" className="text-sm" data-testid={`result-${number}`}>
        {answered && (answered.correct ? "Right!" : `Not quite: the answer is “${options[answered.correctOption - 1]}”.`)}
      </p>
    </div>
  );
}
