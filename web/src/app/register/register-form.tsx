"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Field, FormError, SubmitButton } from "@/components/auth-form";
import { formErrors, type FormErrors } from "@/lib/api/form-errors";

const NO_ERRORS: FormErrors = { form: null, fields: {} };

export function RegisterForm() {
  const [errors, setErrors] = useState(NO_ERRORS);
  const [pending, setPending] = useState(false);
  const router = useRouter();

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/session/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.get("email"),
        password: form.get("password"),
        // The browser's IANA zone, so "today" is the User's today without asking them.
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      }),
    }).catch(() => null);

    if (response?.ok) {
      router.replace("/");
      router.refresh();
      return;
    }
    setPending(false);
    if (!response) setErrors({ form: "CramPlan can't be reached. Check your connection.", fields: {} });
    else if (response.status === 409) {
      setErrors({ form: null, fields: { email: "An account with this email already exists." } });
    } else setErrors(await formErrors(response));
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <FormError message={errors.form ?? errors.fields.timezone ?? null} />
      <Field label="Email" name="email" type="email" autoComplete="email" required error={errors.fields.email} />
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete="new-password"
        required
        minLength={8}
        error={errors.fields.password}
      />
      <p className="-mt-2 text-sm opacity-70">At least 8 characters, with a digit and a symbol.</p>
      <SubmitButton pending={pending}>{pending ? "Creating account…" : "Create account"}</SubmitButton>
      <p className="text-sm">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-blue-700 underline dark:text-blue-400">
          Log in
        </Link>
      </p>
    </form>
  );
}
