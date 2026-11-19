import { unstable_rethrow } from "next/navigation";

import { LogoutButton } from "@/components/logout-button";
import { createUserApiClient } from "@/lib/api/server";

import { site } from "./site";

// A placeholder until onboarding and Today land (#48). Only logged-in Users get here
// (src/proxy.ts).
export default async function Home() {
  const user = await currentUser();

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-4 px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">{site.name}</h1>
      <p className="text-lg">{site.tagline}</p>
      <p className="text-sm opacity-70">
        {user ? (
          <>
            Logged in as <span data-testid="user-email">{user.email}</span>
          </>
        ) : (
          "CramPlan's API can't be reached right now."
        )}
      </p>
      <LogoutButton />
    </main>
  );
}

async function currentUser() {
  try {
    const api = await createUserApiClient("/");
    const { data } = await api.GET("/api/v1/auth/me", { signal: AbortSignal.timeout(2000) });
    return data ?? null;
  } catch (error) {
    unstable_rethrow(error); // The redirect to login, for a token FastAPI refused.
    return null;
  }
}
