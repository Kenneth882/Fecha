import { redirect } from "next/navigation";

import { createUserApiClient } from "@/lib/api/server";
import type { components } from "@/lib/api/schema";

import { activeEvent } from "./active-event";

type EventSummary = components["schemas"]["EventSummary"];

/** A page's API calls give up after this long, rather than leaving it loading. */
const TIMEOUT_MS = 5000;

/**
 * Thrown when FastAPI can't be reached or answers with an error the page can't
 * show. `src/app/error.tsx` renders it.
 */
export class ApiUnavailableError extends Error {
  constructor() {
    super("CramPlan's API can't be reached right now");
  }
}

/**
 * The typed client for a page at `path` (see `createUserApiClient`), with every
 * call's network failure turned into an `ApiUnavailableError`.
 */
export async function pageApi(path: string) {
  const api = await createUserApiClient(path);
  api.use({
    onRequest({ request }) {
      return new Request(request, { signal: AbortSignal.timeout(TIMEOUT_MS) });
    },
    onError() {
      return new ApiUnavailableError();
    },
  });
  return api;
}

export type PageApi = Awaited<ReturnType<typeof pageApi>>;

/** All the logged-in User's Events, newest first. */
export async function loadEvents(api: PageApi): Promise<EventSummary[]> {
  const { data } = await api.GET("/api/v1/events");
  if (!data) throw new ApiUnavailableError();
  return data;
}

/**
 * The logged-in User's Active Event, for a page only they can use (Today, the Plan).
 * A User without one is sent to onboarding.
 */
export async function requireActiveEvent(api: PageApi): Promise<EventSummary> {
  const event = activeEvent(await loadEvents(api));
  if (!event) redirect("/onboarding");
  return event;
}
