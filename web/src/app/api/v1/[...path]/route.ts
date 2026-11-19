import type { NextRequest } from "next/server";

import { apiUrl } from "@/lib/api/client";
import { errorResponse } from "@/lib/api/errors";
import { ACCESS_COOKIE, accessTokenNeedsRefresh } from "@/lib/session/cookies";
import { apiUnreachable } from "@/lib/session/server";

/**
 * Browser code's only way to FastAPI (ADR 0007): `/api/v1/*` here is forwarded to
 * FastAPI's `/api/v1/*`, with the access cookie as `Authorization: Bearer` and no
 * cookies passed on. FastAPI's status, body and request ID come back unchanged.
 *
 * An access token that's missing or within 2 minutes of expiring gets a 401 here, so
 * the browser client refreshes (POST /api/session/refresh) and retries once.
 */
async function forward(request: NextRequest): Promise<Response> {
  const { pathname, search } = request.nextUrl;
  // Their bodies carry tokens, or they need the refresh cookie: browser code uses the
  // /api/session handlers instead.
  if (pathname.startsWith("/api/v1/auth/") && pathname !== "/api/v1/auth/me") {
    return errorResponse(404, "not_found", "Use /api/session to log in, register or log out");
  }

  const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  if (accessTokenNeedsRefresh(accessToken)) {
    return errorResponse(401, "session_refresh_needed", "The session needs refreshing");
  }

  const headers = new Headers({ Authorization: `Bearer ${accessToken}` });
  for (const name of ["Accept", "Content-Type", "X-Request-ID"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const hasBody = request.method !== "GET" && request.method !== "HEAD";

  let upstream: Response;
  try {
    upstream = await fetch(`${apiUrl()}${pathname}${search}`, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return apiUnreachable();
  }

  const responseHeaders = new Headers();
  for (const name of ["Content-Type", "X-Request-ID", "Retry-After"]) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
