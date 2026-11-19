import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { accessTokenExpiringIn } from "@/test/tokens";
import { setCookies, stubFastApi, tokens } from "@/test/fastapi";

import { POST } from "./route";

function logout(cookies: { access?: string; refresh?: string }): NextRequest {
  const request = new NextRequest("http://localhost:3000/api/session/logout", {
    method: "POST",
    headers: { Origin: "http://localhost:3000" },
  });
  if (cookies.access) request.cookies.set("cramplan_access", cookies.access);
  if (cookies.refresh) request.cookies.set("cramplan_refresh", cookies.refresh);
  return request;
}

function expectCleared(response: Response): void {
  const cookies = setCookies(response);
  expect(cookies.get("cramplan_access")?.get("max-age")).toBe("0");
  expect(cookies.get("cramplan_refresh")?.get("max-age")).toBe("0");
  expect(cookies.get("cramplan_refresh")?.get("path")).toBe("/api/session");
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("POST /api/session/logout", () => {
  it("revokes the session at FastAPI and clears both cookies", async () => {
    const access = accessTokenExpiringIn(600);
    const calls = stubFastApi(() => new Response(null, { status: 204 }));

    const response = await POST(logout({ access, refresh: "refresh-token" }));

    expect(calls).toHaveLength(1);
    expect(calls[0].url.pathname).toBe("/api/v1/auth/logout");
    expect(calls[0].headers.get("Authorization")).toBe(`Bearer ${access}`);
    expect(JSON.parse(calls[0].body)).toEqual({ refresh_token: "refresh-token" });
    expect(response.status).toBe(204);
    expectCleared(response);
  });

  it("refreshes a stale access token first, then revokes with the new refresh token", async () => {
    const fresh = accessTokenExpiringIn(1800);
    const calls = stubFastApi((request) =>
      new URL(request.url).pathname === "/api/v1/auth/refresh"
        ? Response.json(tokens({ access_token: fresh, refresh_token: "rotated-refresh" }))
        : new Response(null, { status: 204 }),
    );

    const response = await POST(logout({ access: accessTokenExpiringIn(30), refresh: "old-refresh" }));

    expect(calls.map((call) => call.url.pathname)).toEqual([
      "/api/v1/auth/refresh",
      "/api/v1/auth/logout",
    ]);
    expect(calls[1].headers.get("Authorization")).toBe(`Bearer ${fresh}`);
    expect(JSON.parse(calls[1].body)).toEqual({ refresh_token: "rotated-refresh" });
    expect(response.status).toBe(204);
    expectCleared(response);
  });

  it("just clears the cookies when there's no session to revoke", async () => {
    const calls = stubFastApi(() => new Response(null, { status: 204 }));

    const response = await POST(logout({}));

    expect(calls).toHaveLength(0);
    expect(response.status).toBe(204);
    expectCleared(response);
  });

  it("still clears the cookies when FastAPI can't be reached, but says it couldn't revoke", async () => {
    stubFastApi(() => {
      throw new TypeError("fetch failed");
    });

    const response = await POST(logout({ access: accessTokenExpiringIn(600), refresh: "refresh-token" }));

    expect(response.status).toBe(502);
    expectCleared(response);
  });
});
