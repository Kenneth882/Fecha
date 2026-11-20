"use client";

import { useEffect } from "react";

/**
 * Shown when a page couldn't load, most often because CramPlan's API is down
 * (`ApiUnavailableError`). Server errors reach the browser without their message,
 * so the copy doesn't depend on it.
 */
export default function PageError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-4 px-4 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">This page didn&apos;t load</h1>
      <p className="opacity-80">CramPlan&apos;s API can&apos;t be reached right now. Try again in a moment.</p>
      <button
        type="button"
        onClick={() => retry()}
        className="self-start rounded-md bg-blue-700 px-4 py-2.5 font-medium text-white"
      >
        Try again
      </button>
    </main>
  );
}
