import { NextResponse, type NextRequest } from "next/server";

import { createApiClient } from "@/lib/api/client";
import { errorResponse } from "@/lib/api/errors";
import {
  ACCESS_COOKIE,
  REFRESH_COOKIE,
  accessTokenNeedsRefresh,
  clearSessionCookies,
} from "@/lib/session/cookies";
import { appOrigin } from "@/lib/session/origin";
import { rotateRefreshToken } from "@/lib/session/rotate";
import { callApi } from "@/lib/session/server";

/**
 * Logs out: FastAPI revokes the refresh token's session, so a copied cookie stops
 * working, and both cookies are cleared. FastAPI's logout needs a live access token,
 * so a stale one is refreshed first and the rotated refresh token is revoked instead.
 *
 * 204, or 502 if FastAPI couldn't be reached to revoke (the cookies are cleared anyway).
 */
export async function POST(request: NextRequest): Promise<Response> {
  const revoked = await revokeSession(request);
  const response = revoked
    ? new NextResponse(null, { status: 204 })
    : errorResponse(502, "api_unreachable", "Logged out here, but the session couldn't be ended on the server");
  clearSessionCookies(response, appOrigin(request));
  return response;
}

/** False only when FastAPI couldn't be reached; a session that's already over counts as revoked. */
async function revokeSession(request: NextRequest): Promise<boolean> {
  let accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  let refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return true;

  if (accessTokenNeedsRefresh(accessToken)) {
    const rotation = await rotateRefreshToken(request);
    if (rotation.kind === "unreachable") return false;
    if (rotation.kind === "ended") return true;
    accessToken = rotation.tokens.access_token;
    refreshToken = rotation.tokens.refresh_token;
  }

  const result = await callApi(() =>
    createApiClient().POST("/api/v1/auth/logout", {
      headers: { Authorization: `Bearer ${accessToken}` },
      body: { refresh_token: refreshToken },
    }),
  );
  return result !== null && result.response.status < 500;
}
