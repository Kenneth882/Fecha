import { NextResponse, type NextRequest } from "next/server";

import { errorResponse, type ErrorResponse } from "@/lib/api/errors";

/**
 * Runs one call to FastAPI from a route handler. A network failure (FastAPI down or
 * unreachable) becomes `null`, which the handler answers with `apiUnreachable()`.
 */
export async function callApi<T>(call: () => Promise<T>): Promise<T | null> {
  try {
    return await call();
  } catch {
    return null;
  }
}

export function apiUnreachable(): Response {
  return errorResponse(502, "api_unreachable", "CramPlan's API can't be reached right now");
}

/** FastAPI's error, with its status, body and request ID, as this handler's response. */
export function passError(upstream: Response, error: ErrorResponse | undefined): NextResponse {
  const response = NextResponse.json(error ?? null, { status: upstream.status });
  const requestId = upstream.headers.get("X-Request-ID");
  if (requestId) response.headers.set("X-Request-ID", requestId);
  return response;
}

/**
 * The request's JSON body, unchecked: the handlers pass it on to FastAPI, which
 * validates it and answers 422 with field errors. `undefined` if it isn't JSON.
 */
export async function readJson(request: NextRequest): Promise<unknown> {
  try {
    return await request.json();
  } catch {
    return undefined;
  }
}

export function notJson(): Response {
  return errorResponse(400, "invalid_json", "The request body must be JSON");
}
