import { NextResponse, type NextRequest } from "next/server";

import { errorResponse } from "@/lib/api/errors";
import { ACCESS_COOKIE, accessTokenNeedsRefresh } from "@/lib/session/cookies";
import { appOrigin } from "@/lib/session/origin";

/**
 * The Content-Security-Policy for one response. Scripts run only with this response's
 * nonce, which Next.js reads from the request's CSP header and adds to its own scripts.
 * `connect-src 'self'`: browser code only ever calls this app's origin (ADR 0007).
 */
function contentSecurityPolicy(nonce: string): string {
  // `next dev` needs eval (React's server error stacks) and inline styles (its overlay).
  const isDev = process.env.NODE_ENV === "development";
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' ${isDev ? "'unsafe-inline'" : `'nonce-${nonce}'`}`,
    "img-src 'self' blob: data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

const CHANGING_METHODS = new Set(["POST", "PATCH", "PUT", "DELETE"]);

/**
 * CSRF: a changing request must come from a page of this app. Browsers send `Origin`
 * on every non-GET request, so a missing one is refused too (ADR 0007).
 */
function isForeignChange(request: NextRequest): boolean {
  return (
    CHANGING_METHODS.has(request.method) &&
    request.headers.get("Origin") !== appOrigin(request).origin
  );
}

/**
 * Paths that never need a session: the login and register pages, the route handlers
 * under /api (which answer for themselves), and the PWA's manifest and icons, which
 * must load before anyone logs in.
 *
 * Login stays reachable with a live-looking token too: FastAPI may have refused it
 * (a deleted User, a rotated signing key), and logging in again replaces it.
 */
function isOpenPath(pathname: string): boolean {
  return (
    pathname === "/login" ||
    pathname === "/register" ||
    pathname.startsWith("/api/") ||
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/icons/") ||
    ["/manifest.webmanifest", "/icon.svg", "/apple-icon.png", "/favicon.ico"].includes(pathname)
  );
}

/**
 * A page renders only with an access token that has at least 2 minutes left, so the
 * Server Components behind it can call FastAPI. Otherwise the refresh handler, the
 * only path the refresh cookie is sent to, swaps it and sends the User back here (or
 * on to login, if the session is over).
 */
function sessionRedirect(request: NextRequest): NextResponse | null {
  const { pathname, search } = request.nextUrl;
  if (isOpenPath(pathname)) return null;

  if (!accessTokenNeedsRefresh(request.cookies.get(ACCESS_COOKIE)?.value)) return null;

  const refresh = new URL("/api/session/refresh", appOrigin(request));
  refresh.searchParams.set("next", pathname + search);
  return NextResponse.redirect(refresh);
}

export function proxy(request: NextRequest): Response {
  if (isForeignChange(request)) {
    return errorResponse(403, "cross_origin_request", "Changes can only be made from CramPlan itself");
  }
  const redirect = sessionRedirect(request);
  if (redirect) return redirect;

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const policy = contentSecurityPolicy(nonce);

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("Content-Security-Policy", policy);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  return response;
}

export const config = {
  // Everything but Next.js's hashed build assets, which don't need a policy.
  matcher: ["/((?!_next/static|_next/image).*)"],
};
