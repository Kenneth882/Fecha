import { NextResponse, type NextRequest } from "next/server";

import { errorResponse } from "@/lib/api/errors";
import { clearSessionCookies, setSessionCookies } from "@/lib/session/cookies";
import { safeNextPath } from "@/lib/session/next-path";
import { appOrigin } from "@/lib/session/origin";
import { rotateRefreshToken } from "@/lib/session/rotate";
import { apiUnreachable } from "@/lib/session/server";

/**
 * Silent refresh for browser code: after a 401 from `/api/v1`, the client calls this
 * and retries once. 204 with new session cookies, or 401 with them cleared when the
 * session is over (the client then sends the User to login).
 */
export async function POST(request: NextRequest): Promise<Response> {
  const rotation = await rotateRefreshToken(request);
  if (rotation.kind === "unreachable") return apiUnreachable();

  if (rotation.kind === "ended") {
    const response = errorResponse(401, "session_ended", "Your session has ended: log in again");
    clearSessionCookies(response, appOrigin(request));
    return response;
  }
  const response = new NextResponse(null, { status: 204 });
  setSessionCookies(response, rotation.tokens, appOrigin(request));
  return response;
}

/**
 * Silent refresh for a page load: the proxy sends a request whose access token is
 * missing or about to expire here, the only path the refresh cookie reaches, and this
 * sends the User back to `next` (or to login once the session is over).
 *
 * A GET that rotates the token is safe from CSRF: another site can make a browser load
 * it, but that only gives the User's own browser new cookies, and the redirect never
 * leaves this origin.
 */
export async function GET(request: NextRequest): Promise<Response> {
  const next = safeNextPath(request.nextUrl.searchParams.get("next"));
  const rotation = await rotateRefreshToken(request);

  if (rotation.kind === "rotated") {
    const response = NextResponse.redirect(new URL(next, appOrigin(request)));
    setSessionCookies(response, rotation.tokens, appOrigin(request));
    return response;
  }
  if (rotation.kind === "unreachable") {
    // Not the User's fault, and their session may be fine: say so, and keep the cookies.
    return apiUnreachable();
  }

  const login = new URL("/login", appOrigin(request));
  if (next !== "/") login.searchParams.set("next", next);
  const response = NextResponse.redirect(login);
  clearSessionCookies(response, appOrigin(request));
  return response;
}
