import { formErrorsFromBody } from "@/lib/api/form-errors";

export type CompletionOutcome = { kind: "today" } | { kind: "error"; message: string };

/**
 * What the Done button does with POST /tasks/{id}/complete's response: its status
 * (`null` if it never arrived) and parsed body. Completing is idempotent, so any
 * success goes to Today. A 409 (Missed, or for a later Plan Day) shows FastAPI's reason.
 */
export function completionOutcome(status: number | null, body: unknown): CompletionOutcome {
  if (status === null) return { kind: "error", message: "CramPlan can't be reached. Check your connection." };
  if (status >= 200 && status < 300) return { kind: "today" };
  const { form, fields } = formErrorsFromBody(body);
  return { kind: "error", message: form ?? Object.values(fields)[0] };
}
