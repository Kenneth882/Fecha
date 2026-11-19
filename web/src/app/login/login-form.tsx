"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Field, FormError, SubmitButton } from "@/components/auth-form";
import { formErrors, type FormErrors } from "@/lib/api/form-errors";

const NO_ERRORS: FormErrors = { form: null, fields: {} };

/** `next` has already been checked to be a path on this app (`safeNextPath`). */
export function LoginForm({ next }: { next: string }) {
  const [errors, setErrors] = useState(NO_ERRORS);
  const [pending, setPending] = useState(false);
  const router = useRouter();

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/session/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
    }).catch(() => null);

    if (response?.ok) {
      // refresh() drops any page the router cached before the new session.
      router.replace(next);
      router.refresh();
      return;
    }
    setPending(false);
    if (!response) setErrors({ form: "CramPlan can't be reached. Check your connection.", fields: {} });
    else if (response.status === 401) setErrors({ form: "Wrong email or password.", fields: {} });
    else setErrors(await formErrors(response));
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <FormError message={errors.form} />
      <Field label="Email" name="email" type="email" autoComplete="email" required error={errors.fields.email} />
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete="current-password"
        required
        error={errors.fields.password}
      />
      <SubmitButton pending={pending}>{pending ? "Logging in…" : "Log in"}</SubmitButton>
      <p className="text-sm">
        New to CramPlan?{" "}
        <Link href="/register" className="font-medium text-blue-700 underline dark:text-blue-400">
          Create an account
        </Link>
      </p>
    </form>
  );
}
