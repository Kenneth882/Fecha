/** What POST /api/session/refresh came back with. */
export type RefreshOutcome = "rotated" | "ended" | "unreachable";

type Fetch = (request: Request) => Promise<Response>;

/**
 * Silent refresh for browser code (ADR 0007). A 401 from `/api/v1` means the access
 * token is missing or about to expire, so this refreshes the session and retries the
 * request exactly once. If the refresh says the session is over, or the retry still
 * gets a 401, `onSessionEnded` runs (the app sends the User to login).
 *
 * Requests that get a 401 together share one refresh: two refreshes racing with the
 * same refresh token would look like token theft to the API.
 */
export function withSilentRefresh(deps: {
  fetch: Fetch;
  refresh: () => Promise<RefreshOutcome>;
  onSessionEnded: () => void;
}): Fetch {
  let refreshing: Promise<RefreshOutcome> | null = null;

  const refreshOnce = (): Promise<RefreshOutcome> => {
    refreshing ??= deps.refresh().finally(() => {
      refreshing = null;
    });
    return refreshing;
  };

  return async (request) => {
    const retry = request.clone(); // Before the first send, which consumes the body.
    const response = await deps.fetch(request);
    if (response.status !== 401) return response;

    const outcome = await refreshOnce();
    if (outcome === "unreachable") return response;
    if (outcome === "ended") {
      deps.onSessionEnded();
      return response;
    }

    const retried = await deps.fetch(retry);
    if (retried.status === 401) deps.onSessionEnded();
    return retried;
  };
}
