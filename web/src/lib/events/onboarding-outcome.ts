import type { ErrorResponse } from "@/lib/api/errors";
import { formErrorsFromBody, type FormErrors } from "@/lib/api/form-errors";

export type OnboardingOutcome = { kind: "today" } | { kind: "errors"; errors: FormErrors };

/**
 * What onboarding does with POST /events's response: its status (`null` if it never
 * arrived) and parsed body. A 409 means the User already has an Active Event
 * (ADR 0001), so they go to Today just as if this one was created. FastAPI's
 * out-of-range Event Day error is for the body as a whole, so it's placed on the
 * Event Day field here.
 */
export function onboardingOutcome(status: number | null, body: unknown): OnboardingOutcome {
  if (status === null) {
    return { kind: "errors", errors: { form: "CramPlan can't be reached. Check your connection.", fields: {} } };
  }
  if ((status >= 200 && status < 300) || status === 409) return { kind: "today" };

  const error = (body as ErrorResponse | null | undefined)?.error;
  if (error?.code === "event_day_out_of_range") {
    return { kind: "errors", errors: { form: null, fields: { event_day: error.message } } };
  }
  return { kind: "errors", errors: formErrorsFromBody(body) };
}
