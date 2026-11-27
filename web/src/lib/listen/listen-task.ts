import type { ErrorResponse } from "@/lib/api/errors";
import { formErrorsFromBody } from "@/lib/api/form-errors";
import type { components } from "@/lib/api/schema";

type ListenTask = components["schemas"]["ListenTask"];
export type ListenAnswerResult = components["schemas"]["ListenAnswerResult"];

/**
 * A Comprehension Question on screen. Open: it can be answered. Sending: a choice is
 * on its way, so another tap does nothing. Answered: final, with the correct option.
 * Locked: the Task is read-only (Missed, or another day's) and it wasn't answered.
 */
export type QuestionState =
  | { kind: "open" }
  | { kind: "sending"; choice: number }
  | { kind: "answered"; choice: number; correct: boolean; correctOption: number }
  | { kind: "locked" };

export type ListenState = {
  /** By question number, from 1. */
  questions: Record<number, QuestionState>;
  completed: boolean;
  /** Why the last answer wasn't saved, until the next choice. */
  error: string | null;
};

export type ListenAction =
  | { type: "choose"; question: number; choice: number }
  | { type: "answered"; result: ListenAnswerResult }
  | { type: "failed"; question: number; message: string }
  /** The Task reloaded after a lost reply: what FastAPI saved replaces the screen's view. */
  | { type: "sync"; task: ListenTask };

/** The screen's state for the Task as GET /tasks/{id}/listen returned it. */
export function startListen(task: ListenTask): ListenState {
  const questions: Record<number, QuestionState> = {};
  for (const { number, answer } of task.questions) {
    questions[number] = answer
      ? { kind: "answered", choice: answer.choice, correct: answer.correct, correctOption: answer.correct_option }
      : task.answerable
        ? { kind: "open" }
        : { kind: "locked" };
  }
  return { questions, completed: task.status === "completed", error: null };
}

/**
 * Only an open question takes a choice, and it stays Sending until FastAPI answers, so
 * a double tap sends one answer. The reveal comes from FastAPI's reply: the screen
 * never knows the correct option before then.
 */
export function nextListenState(state: ListenState, action: ListenAction): ListenState {
  switch (action.type) {
    case "choose":
      if (state.questions[action.question]?.kind !== "open") return state;
      return {
        ...state,
        questions: { ...state.questions, [action.question]: { kind: "sending", choice: action.choice } },
        error: null,
      };
    case "answered": {
      const { question, choice, correct, correct_option, status } = action.result;
      return {
        ...state,
        questions: { ...state.questions, [question]: { kind: "answered", choice, correct, correctOption: correct_option } },
        completed: status === "completed",
      };
    }
    case "failed":
      return {
        ...state,
        questions: { ...state.questions, [action.question]: { kind: "open" } },
        error: action.message,
      };
    case "sync":
      return startListen(action.task);
  }
}

export type AnswerOutcome =
  | { kind: "answered"; result: ListenAnswerResult }
  /** FastAPI already has an answer for this question: an earlier reply was lost. */
  | { kind: "alreadyAnswered" }
  | { kind: "error"; message: string };

/** POST /tasks/{id}/answers's reply, as openapi-fetch returns it; `null` if none arrived. */
export type AnswerReply = { data?: ListenAnswerResult; error?: unknown } | null;

/**
 * What an answer's reply means. A refusal (a 409: answered already, Missed, another
 * day's) shows FastAPI's reason.
 */
export function answerOutcome(reply: AnswerReply): AnswerOutcome {
  if (reply === null) return { kind: "error", message: "CramPlan can't be reached. Check your connection." };
  if (reply.data) return { kind: "answered", result: reply.data };
  if ((reply.error as ErrorResponse | undefined)?.error?.code === "question_already_answered") {
    return { kind: "alreadyAnswered" };
  }
  const { form, fields } = formErrorsFromBody(reply.error);
  return { kind: "error", message: form ?? Object.values(fields)[0] };
}

/**
 * Why the Task's questions can't be answered here, or null if they can or it's done
 * (the screen shows a completed Task as done instead). `pastEvent`: the Task isn't
 * part of the User's Active Event. FastAPI's `status` doesn't say, so the page does.
 */
export function readOnlyMessage(
  task: Pick<ListenTask, "status" | "answerable">,
  { pastEvent }: { pastEvent: boolean },
): string | null {
  if (task.answerable || task.status === "completed") return null;
  if (pastEvent) return "This Task is part of a past Event, so its questions can't be answered any more.";
  return task.status === "missed"
    ? "This Task was missed: its Plan Day has passed, so its questions can't be answered any more."
    : "This Task isn't one of today's. You can answer its questions on its Plan Day.";
}
