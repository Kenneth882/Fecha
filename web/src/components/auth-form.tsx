import type { ReactNode } from "react";

/** The shared frame of the login and register screens. */
export function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-6 px-4 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {children}
    </main>
  );
}

export function Field({
  label,
  error,
  ...input
}: { label: string; error?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  const errorId = error ? `${input.name}-error` : undefined;
  return (
    <label className="flex flex-col gap-1 text-sm font-medium">
      {label}
      <input
        {...input}
        aria-invalid={error ? true : undefined}
        aria-describedby={errorId}
        className="rounded-md border border-current/25 bg-transparent px-3 py-2 text-base font-normal outline-none focus:border-blue-600 aria-invalid:border-red-600"
      />
      {error && (
        <span id={errorId} className="text-sm font-normal text-red-600">
          {error}
        </span>
      )}
    </label>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-md bg-red-600/10 px-3 py-2 text-sm text-red-700 dark:text-red-400">
      {message}
    </p>
  );
}

export function SubmitButton({ pending, children }: { pending: boolean; children: ReactNode }) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-md bg-blue-700 px-4 py-2.5 font-medium text-white disabled:opacity-60"
    >
      {children}
    </button>
  );
}
