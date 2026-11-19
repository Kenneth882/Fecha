import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiError, setCookies, stubFastApi, tokens } from "@/test/fastapi";

import { POST } from "./route";

const newUser = { email: "ana@example.com", password: "s3cret-Password", timezone: "Europe/Madrid" };

const profile = {
  id: "8f9e4c1a-0000-4000-8000-000000000001",
  email: "ana@example.com",
  timezone: "Europe/Madrid",
  native_language: "en",
  role: "user",
  created_at: "2026-11-19T10:00:00Z",
};

function register(): NextRequest {
  return new NextRequest("http://localhost:3000/api/session/register", {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: "http://localhost:3000" },
    body: JSON.stringify(newUser),
  });
}

function fastApi(registerResponse: () => Response) {
  return stubFastApi((request) =>
    new URL(request.url).pathname === "/api/v1/auth/register"
      ? registerResponse()
      : Response.json(tokens({ access_token: "access-jwt", refresh_token: "refresh-token" })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("POST /api/session/register", () => {
  it("registers the User and logs them straight in", async () => {
    const calls = fastApi(() => Response.json(profile, { status: 201 }));

    const response = await POST(register());

    expect(calls.map((call) => call.url.pathname)).toEqual([
      "/api/v1/auth/register",
      "/api/v1/auth/login",
    ]);
    expect(JSON.parse(calls[0].body)).toEqual(newUser);
    expect(JSON.parse(calls[1].body)).toEqual({ email: newUser.email, password: newUser.password });
    expect(response.status).toBe(201);
    const cookies = setCookies(response);
    expect(cookies.get("cramplan_access")?.get("value")).toBe("access-jwt");
    expect(cookies.get("cramplan_refresh")?.get("path")).toBe("/api/session");
  });

  it("returns the profile but no token", async () => {
    fastApi(() => Response.json(profile, { status: 201 }));

    const body = await (await POST(register())).text();

    expect(JSON.parse(body)).toEqual(profile);
    expect(body).not.toContain("access-jwt");
    expect(body).not.toContain("refresh-token");
  });

  it.each([
    [422, "validation_error"],
    [409, "email_taken"],
  ])("passes FastAPI's %i through, without logging in", async (status, code) => {
    const calls = fastApi(() => apiError(status, code));

    const response = await POST(register());

    expect(response.status).toBe(status);
    expect((await response.json()).error.code).toBe(code);
    expect(calls).toHaveLength(1);
    expect(response.headers.getSetCookie()).toEqual([]);
  });
});
