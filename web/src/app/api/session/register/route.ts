import { NextResponse, type NextRequest } from "next/server";

import { createApiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { setSessionCookies } from "@/lib/session/cookies";
import { appOrigin } from "@/lib/session/origin";
import { apiUnreachable, callApi, notJson, passError, readJson } from "@/lib/session/server";

type UserCreate = components["schemas"]["UserCreate"];

/**
 * Registers a User and logs them straight in: 201 with their profile, and the tokens
 * in the session cookies only (ADR 0007). FastAPI's 422 (field errors) and 409 (email
 * taken) are passed through for the form to show.
 */
export async function POST(request: NextRequest): Promise<Response> {
  // FastAPI validates it, answering 422 for anything malformed.
  const newUser = (await readJson(request)) as UserCreate | undefined;
  if (newUser === undefined) return notJson();

  const api = createApiClient();
  const registered = await callApi(() => api.POST("/api/v1/auth/register", { body: newUser }));
  if (!registered) return apiUnreachable();
  if (!registered.data) return passError(registered.response, registered.error);

  const loggedIn = await callApi(() =>
    api.POST("/api/v1/auth/login", {
      body: { email: newUser.email, password: newUser.password },
    }),
  );
  if (!loggedIn) return apiUnreachable();
  if (!loggedIn.data) return passError(loggedIn.response, loggedIn.error);

  const response = NextResponse.json(registered.data, { status: 201 });
  setSessionCookies(response, loggedIn.data, appOrigin(request));
  return response;
}
