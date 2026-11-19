import type { ErrorResponse } from "./errors";

export type FormErrors = {
  /** For the form as a whole, e.g. "Wrong email or password". */
  form: string | null;
  /** Per field, keyed by FastAPI's `field` (`email`, `password`, …). */
  fields: Record<string, string>;
};

/** A failed response's `ErrorResponse`, shaped for showing inline on a form. */
export async function formErrors(response: Response): Promise<FormErrors> {
  const body = (await response.json().catch(() => null)) as ErrorResponse | null;
  if (!body?.error) {
    return { form: "Something went wrong. Please try again.", fields: {} };
  }
  const fields: Record<string, string> = {};
  for (const detail of body.error.details) {
    if (detail.field && !(detail.field in fields)) fields[detail.field] = detail.message;
  }
  const form = Object.keys(fields).length > 0 ? null : body.error.message;
  return { form, fields };
}
