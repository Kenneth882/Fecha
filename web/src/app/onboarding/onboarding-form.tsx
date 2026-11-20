"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import { FormError, SubmitButton } from "@/components/auth-form";
import { createBrowserApiClient } from "@/lib/api/browser";
import type { FormErrors } from "@/lib/api/form-errors";
import type { components } from "@/lib/api/schema";
import type { EventDayRange } from "@/lib/events/event-day-range";
import { EVENT_TYPES, LEVELS, formatDate } from "@/lib/events/labels";
import { onboardingOutcome } from "@/lib/events/onboarding-outcome";

type EventCreate = components["schemas"]["EventCreate"];

const NO_ERRORS: FormErrors = { form: null, fields: {} };
const BUDGETS: EventCreate["daily_budget"][] = [15, 30, 45];
const MAX_GOALS = 500;

/** `range` is the Event Days FastAPI accepts, from the User's local today. */
export function OnboardingForm({ range }: { range: EventDayRange }) {
  const [errors, setErrors] = useState(NO_ERRORS);
  const [pending, setPending] = useState(false);
  const [goals, setGoals] = useState("");
  const router = useRouter();

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    const form = new FormData(event.currentTarget);
    const goalsText = String(form.get("goals") ?? "").trim();
    // Unchecked here: FastAPI validates it and answers 422 with field errors.
    const body = {
      type: form.get("type"),
      target_language: "es",
      event_day: form.get("event_day"),
      level: form.get("level"),
      daily_budget: Number(form.get("daily_budget")),
      goals: goalsText || null,
    } as EventCreate;

    const result = await createBrowserApiClient()
      .POST("/api/v1/events", { body })
      .catch(() => null);
    const outcome = onboardingOutcome(result?.response.status ?? null, result?.error);

    if (outcome.kind === "today") {
      router.replace("/today");
      router.refresh();
      return;
    }
    setPending(false);
    setErrors(outcome.errors);
  }

  const fields = errors.fields;
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-6" noValidate>
      <FormError message={errors.form} />

      <Choices legend="What are you preparing for?" error={fields.type} name="type">
        {Object.entries(EVENT_TYPES).map(([value, { label, description }], index) => (
          <Choice key={value} name="type" value={value} defaultChecked={index === 0} label={label}>
            {description}
          </Choice>
        ))}
      </Choices>

      <div className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Language</span>
        <span className="opacity-80">Spanish (more languages later)</span>
      </div>

      <label className="flex flex-col gap-1 text-sm font-medium">
        When is it?
        <input
          type="date"
          name="event_day"
          required
          min={range.min}
          max={range.max}
          aria-invalid={fields.event_day ? true : undefined}
          aria-describedby="event_day-hint"
          className="rounded-md border border-current/25 bg-transparent px-3 py-2 text-base font-normal outline-none focus:border-blue-600 aria-invalid:border-red-600"
        />
        <span id="event_day-hint" className={fields.event_day ? "font-normal text-red-600" : "font-normal opacity-70"}>
          {fields.event_day ?? `Between ${formatDate(range.min)} and ${formatDate(range.max, { year: true })}.`}
        </span>
      </label>

      <Choices legend="Your Spanish level" error={fields.level} name="level">
        {Object.entries(LEVELS).map(([value, { label, description }]) => (
          <Choice key={value} name="level" value={value} defaultChecked={value === "A2"} label={label}>
            {description}
          </Choice>
        ))}
      </Choices>

      <Choices legend="Time per day" error={fields.daily_budget} name="daily_budget" row>
        {BUDGETS.map((minutes) => (
          <Choice key={minutes} name="daily_budget" value={String(minutes)} defaultChecked={minutes === 30} label={`${minutes} min`} />
        ))}
      </Choices>

      <label className="flex flex-col gap-1 text-sm font-medium">
        Your goals (optional)
        <textarea
          name="goals"
          rows={3}
          maxLength={MAX_GOALS}
          value={goals}
          onChange={(event) => setGoals(event.target.value)}
          placeholder="e.g. Talk confidently about my last project"
          aria-invalid={fields.goals ? true : undefined}
          aria-describedby="goals-hint"
          className="rounded-md border border-current/25 bg-transparent px-3 py-2 text-base font-normal outline-none focus:border-blue-600 aria-invalid:border-red-600"
        />
        <span id="goals-hint" className={fields.goals ? "font-normal text-red-600" : "font-normal opacity-70"}>
          {fields.goals ?? `${goals.length} / ${MAX_GOALS}`}
        </span>
      </label>

      <SubmitButton pending={pending}>{pending ? "Building your Plan…" : "Build my Plan"}</SubmitButton>
    </form>
  );
}

function Choices({
  legend,
  name,
  error,
  row = false,
  children,
}: {
  legend: string;
  name: string;
  error?: string;
  row?: boolean;
  children: ReactNode;
}) {
  return (
    <fieldset className="flex flex-col gap-2" aria-describedby={error ? `${name}-error` : undefined}>
      <legend className="mb-2 text-sm font-medium">{legend}</legend>
      <div className={row ? "grid grid-cols-3 gap-2" : "flex flex-col gap-2"}>{children}</div>
      {error && (
        <span id={`${name}-error`} className="text-sm text-red-600">
          {error}
        </span>
      )}
    </fieldset>
  );
}

function Choice({
  name,
  value,
  label,
  defaultChecked,
  children,
}: {
  name: string;
  value: string;
  label: string;
  defaultChecked?: boolean;
  children?: ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-md border border-current/20 px-3 py-2.5 has-checked:border-blue-600 has-checked:bg-blue-600/5">
      <input type="radio" name={name} value={value} defaultChecked={defaultChecked} className="mt-1 accent-blue-700" />
      <span className="flex flex-col">
        <span className="font-medium">{label}</span>
        {children && <span className="text-sm opacity-75">{children}</span>}
      </span>
    </label>
  );
}
