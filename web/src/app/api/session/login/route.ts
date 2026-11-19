import { NextResponse, type NextRequest } from "next/server";

import { createApiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { setSessionCookies } from "@/lib/session/cookies";
import { appOrigin } from "@/lib/session/origin";
import { apiUnreachable, callApi, notJson, passError, readJson } from "@/lib/session/server";

/**
 * Logs in: FastAPI checks the email and password, and its tokens go into the session
 * cookies, never into the response body (ADR 0007). 204 on success; FastAPI's error
 * (401, 422) is passed through otherwise.
 */
export async function POST(request: NextRequest): Promise<Response> {
  const credentials = await readJson(request);
  if (credentials === undefined) return notJson();

  const result = await callApi(() =>
    createApiClient().POST("/api/v1/auth/login", {
      // FastAPI validates it, answering 422 for anything malformed.
      body: credentials as components["schemas"]["LoginRequest"],
    }),
  );
  if (!result) return apiUnreachable();
  if (!result.data) return passError(result.response, result.error);

  const response = new NextResponse(null, { status: 204 });
  setSessionCookies(response, result.data, appOrigin(request));
  return response;
}
