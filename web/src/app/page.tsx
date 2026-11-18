import { createApiClient } from "@/lib/api/client";

// A placeholder until the login, onboarding and Today screens land (#47-#50).
export default async function Home() {
  const apiUp = await apiIsLive();

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-4 px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">CramPlan</h1>
      <p className="text-lg">
        A day-by-day cram plan for one real event, by one fixed date.
      </p>
      <p className="text-sm opacity-70">
        API: <span data-testid="api-status">{apiUp ? "up" : "unreachable"}</span>
      </p>
    </main>
  );
}

async function apiIsLive(): Promise<boolean> {
  try {
    const { data } = await createApiClient().GET("/api/v1/health", {
      signal: AbortSignal.timeout(2000),
    });
    return data?.status === "ok";
  } catch {
    return false;
  }
}
