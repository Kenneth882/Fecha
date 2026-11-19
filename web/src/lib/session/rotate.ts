import type { NextRequest } from "next/server";

import { createApiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

import { REFRESH_COOKIE } from "./cookies";
import { callApi } from "./server";

export type Rotation =
  | { kind: "rotated"; tokens: components["schemas"]["TokenResponse"] }
  /** No refresh cookie, or FastAPI refused it: the User has to log in again. */
  | { kind: "ended" }
  /** FastAPI couldn't be reached; the session may well still be good. */
  | { kind: "unreachable" };

/** Swaps the request's refresh cookie for new tokens at FastAPI's `/auth/refresh`. */
export async function rotateRefreshToken(request: NextRequest): Promise<Rotation> {
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return { kind: "ended" };

  const result = await callApi(() =>
    createApiClient().POST("/api/v1/auth/refresh", { body: { refresh_token: refreshToken } }),
  );
  if (!result) return { kind: "unreachable" };
  if (result.response.status >= 500) return { kind: "unreachable" };
  return result.data ? { kind: "rotated", tokens: result.data } : { kind: "ended" };
}
