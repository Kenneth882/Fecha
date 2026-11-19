import { describe, expect, it, vi } from "vitest";

import { withSilentRefresh, type RefreshOutcome } from "./session-fetch";

function api(...statuses: number[]) {
  const seen: { url: string; body: string }[] = [];
  const fetch = vi.fn(async (request: Request) => {
    seen.push({ url: request.url, body: await request.text() });
    return new Response(null, { status: statuses.shift() ?? 200 });
  });
  return { fetch, seen };
}

function setup(statuses: number[], refreshOutcome: RefreshOutcome = "rotated") {
  const { fetch, seen } = api(...statuses);
  const refresh = vi.fn(async () => refreshOutcome);
  const onSessionEnded = vi.fn();
  const sessionFetch = withSilentRefresh({ fetch, refresh, onSessionEnded });
  return { sessionFetch, fetch, seen, refresh, onSessionEnded };
}

const request = () =>
  new Request("http://localhost:3000/api/v1/reviews/r1/grade", {
    method: "POST",
    body: JSON.stringify({ grade: 4 }),
  });

describe("withSilentRefresh", () => {
  it("returns a successful response untouched, without refreshing", async () => {
    const { sessionFetch, refresh } = setup([200]);

    const response = await sessionFetch(request());

    expect(response.status).toBe(200);
    expect(refresh).not.toHaveBeenCalled();
  });

  it("refreshes on a 401 and retries the same request once, body included", async () => {
    const { sessionFetch, seen, refresh } = setup([401, 201]);

    const response = await sessionFetch(request());

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(response.status).toBe(201);
    expect(seen).toHaveLength(2);
    expect(seen[1]).toEqual(seen[0]);
    expect(JSON.parse(seen[1].body)).toEqual({ grade: 4 });
  });

  it("retries exactly once: a second 401 ends the session instead of looping", async () => {
    const { sessionFetch, fetch, refresh, onSessionEnded } = setup([401, 401, 401]);

    const response = await sessionFetch(request());

    expect(fetch).toHaveBeenCalledTimes(2);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(response.status).toBe(401);
    expect(onSessionEnded).toHaveBeenCalledTimes(1);
  });

  it("doesn't retry, and ends the session, when the refresh says it's over", async () => {
    const { sessionFetch, fetch, onSessionEnded } = setup([401], "ended");

    const response = await sessionFetch(request());

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(response.status).toBe(401);
    expect(onSessionEnded).toHaveBeenCalledTimes(1);
  });

  it("keeps the session when the refresh only failed to reach the API", async () => {
    const { sessionFetch, fetch, onSessionEnded } = setup([401], "unreachable");

    const response = await sessionFetch(request());

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(response.status).toBe(401);
    expect(onSessionEnded).not.toHaveBeenCalled();
  });

  it("shares one refresh between requests that get a 401 at the same time", async () => {
    let finishRefresh: (outcome: RefreshOutcome) => void = () => {};
    const refresh = vi.fn(
      () => new Promise<RefreshOutcome>((resolve) => (finishRefresh = resolve)),
    );
    const statuses = [401, 401, 200, 200];
    const fetch = vi.fn(async () => new Response(null, { status: statuses.shift() }));
    const sessionFetch = withSilentRefresh({ fetch, refresh, onSessionEnded: vi.fn() });

    const both = Promise.all([sessionFetch(request()), sessionFetch(request())]);
    await vi.waitFor(() => expect(refresh).toHaveBeenCalled());
    finishRefresh("rotated");
    const responses = await both;

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(responses.map((response) => response.status)).toEqual([200, 200]);
  });

  it("refreshes again for a later 401, once the earlier refresh is done", async () => {
    const { sessionFetch, refresh } = setup([401, 200, 401, 200]);

    await sessionFetch(request());
    await sessionFetch(request());

    expect(refresh).toHaveBeenCalledTimes(2);
  });
});
