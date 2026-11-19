import createClient from "openapi-fetch";

import type { paths } from "./schema";
import { withSilentRefresh, type RefreshOutcome } from "./session-fetch";

/**
 * The typed API client for browser code (Client Components). It calls this app's own
 * `/api/v1`, which the Next.js server forwards to FastAPI with the session's access
 * token (ADR 0007); a 401 refreshes the session silently and retries once.
 */
export function createBrowserApiClient() {
  return createClient<paths>({
    baseUrl: window.location.origin,
    fetch: withSilentRefresh({
      fetch: (request) => fetch(request),
      refresh: refreshSession,
      onSessionEnded: goToLogin,
    }),
  });
}

async function refreshSession(): Promise<RefreshOutcome> {
  try {
    const response = await fetch("/api/session/refresh", { method: "POST" });
    if (response.ok) return "rotated";
    return response.status === 401 ? "ended" : "unreachable";
  } catch {
    return "unreachable";
  }
}

/** To login, coming back to this page afterwards (login checks `next` is a path here). */
function goToLogin(): void {
  const here = window.location.pathname + window.location.search;
  // A full load, not a router push: it drops everything the ended session rendered.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${encodeURIComponent(here)}`);
}
