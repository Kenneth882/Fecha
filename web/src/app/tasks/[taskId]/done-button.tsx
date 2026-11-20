"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { FormError } from "@/components/auth-form";
import { createBrowserApiClient } from "@/lib/api/browser";
import { completionOutcome } from "@/lib/tasks/completion-outcome";

/** Completes the Vocab Task, introducing its batch, and goes back to Today. */
export function DoneButton({ taskId }: { taskId: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function onClick() {
    setPending(true);
    setError(null);
    const result = await createBrowserApiClient()
      .POST("/api/v1/tasks/{task_id}/complete", { params: { path: { task_id: taskId } } })
      .catch(() => null);
    const outcome = completionOutcome(result?.response.status ?? null, result?.error);

    if (outcome.kind === "today") {
      router.replace("/today");
      router.refresh();
      return;
    }
    setPending(false);
    setError(outcome.message);
  }

  return (
    <div className="flex flex-col gap-3">
      <FormError message={error} />
      <button
        type="button"
        onClick={onClick}
        disabled={pending}
        data-testid="task-done"
        className="rounded-md bg-blue-700 px-4 py-3 font-medium text-white disabled:opacity-60"
      >
        {pending ? "Saving…" : "Done"}
      </button>
    </div>
  );
}
