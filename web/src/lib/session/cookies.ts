import type { NextResponse } from "next/server";

import type { components } from "@/lib/api/schema";

type TokenResponse = components["schemas"]["TokenResponse"];

/** The access JWT, which the proxy copies into `Authorization: Bearer` (ADR 0007). */
export const ACCESS_COOKIE = "cramplan_access";
/** The refresh token, sent only to the session route handlers. */
export const REFRESH_COOKIE = "cramplan_refresh";

/**
 * The refresh cookie's path: every session handler (login, register, refresh, logout)
 * needs it, but no page or `/api/v1` request ever carries it.
 */
export const REFRESH_COOKIE_PATH = "/api/session";

/** Refresh this long before the access token expires, so a page never renders on a dying one. */
export const REFRESH_MARGIN_SECONDS = 120;

/**
 * Whether cookies get `Secure`. Everywhere but localhost, which is served over plain
 * HTTP in development and compose.
 */
export function isSecureOrigin(origin: URL): boolean {
  return !["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname);
}

/** Sets both session cookies from FastAPI's token response; `origin` is `appOrigin(request)`. */
export function setSessionCookies(response: NextResponse, tokens: TokenResponse, origin: URL): void {
  const base = { httpOnly: true, secure: isSecureOrigin(origin), sameSite: "lax" } as const;
  response.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    ...base,
    path: "/",
    maxAge: tokens.expires_in,
  });
  response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
    ...base,
    path: REFRESH_COOKIE_PATH,
    maxAge: tokens.refresh_expires_in,
  });
}

/** Expires both session cookies, at the same paths they were set on. */
export function clearSessionCookies(response: NextResponse, origin: URL): void {
  const base = { httpOnly: true, secure: isSecureOrigin(origin), sameSite: "lax", maxAge: 0 } as const;
  response.cookies.set(ACCESS_COOKIE, "", { ...base, path: "/" });
  response.cookies.set(REFRESH_COOKIE, "", { ...base, path: REFRESH_COOKIE_PATH });
}

/**
 * Whether an access token is missing, unreadable, or within `REFRESH_MARGIN_SECONDS`
 * of its `exp`. Only `exp` is read, and the signature isn't checked: FastAPI does that,
 * and a forged token just gets a 401 there.
 */
export function accessTokenNeedsRefresh(token: string | undefined, nowMs = Date.now()): boolean {
  if (!token) return true;
  const exp = expiresAt(token);
  return exp === null || exp - nowMs / 1000 < REFRESH_MARGIN_SECONDS;
}

function expiresAt(token: string): number | null {
  const payload = token.split(".")[1];
  if (!payload) return null;
  try {
    const claims: unknown = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    if (typeof claims === "object" && claims !== null && "exp" in claims) {
      return typeof claims.exp === "number" ? claims.exp : null;
    }
    return null;
  } catch {
    return null;
  }
}
