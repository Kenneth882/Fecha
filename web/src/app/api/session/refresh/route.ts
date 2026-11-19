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
    return unavailablePage(next);
  }

  const login = new URL("/login", appOrigin(request));
  if (next !== "/") login.searchParams.set("next", next);
  const response = NextResponse.redirect(login);
  clearSessionCookies(response, appOrigin(request));
  return response;
}

/**
 * What a page load shows while FastAPI is down: this is a navigation, so a JSON error
 * would appear raw. Plain HTML, no scripts or inline styles (the CSP allows neither).
 */
function unavailablePage(next: string): Response {
  const href = escapeHtml(next);
  const html = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CramPlan is unavailable</title></head>
<body>
<main>
<h1>CramPlan can't be reached right now</h1>
<p>You're still logged in. Try again in a moment.</p>
<p><a href="${href}">Try again</a></p>
</main>
</body>
</html>`;
  return new Response(html, {
    status: 503,
    headers: { "Content-Type": "text/html; charset=utf-8", "Retry-After": "10" },
  });
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
