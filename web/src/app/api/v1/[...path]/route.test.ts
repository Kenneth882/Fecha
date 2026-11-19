import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { accessTokenExpiringIn } from "@/test/tokens";
import { API_URL, apiError, stubFastApi } from "@/test/fastapi";

import { DELETE, GET, PATCH, POST } from "./route";

function apiRequest(
  path: string,
  init: { method?: string; body?: string; access?: string; headers?: Record<string, string> } = {},
): NextRequest {
  const request = new NextRequest(`http://localhost:3000${path}`, {
    method: init.method ?? "GET",
    body: init.body,
    headers: { Origin: "http://localhost:3000", ...init.headers },
  });
  if (init.access) request.cookies.set("cramplan_access", init.access);
  request.cookies.set("other", "cookie");
  return request;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the /api/v1 proxy to FastAPI", () => {
  it("copies the access cookie into a Bearer header, and sends no cookies on", async () => {
    const access = accessTokenExpiringIn(600);
    const calls = stubFastApi(() => Response.json({ id: "event-1" }));

    await GET(apiRequest("/api/v1/events/active", { access }));

    expect(calls).toHaveLength(1);
    expect(calls[0].url.href).toBe(`${API_URL}/api/v1/events/active`);
    expect(calls[0].headers.get("Authorization")).toBe(`Bearer ${access}`);
    expect(calls[0].headers.get("Cookie")).toBeNull();
  });

  it("forwards the method, query string and JSON body", async () => {
    const calls = stubFastApi(() => Response.json({}, { status: 201 }));

    await POST(
      apiRequest("/api/v1/reviews/abc/grade?source=queue", {
        method: "POST",
        access: accessTokenExpiringIn(600),
        body: JSON.stringify({ grade: 4 }),
        headers: { "Content-Type": "application/json" },
      }),
    );

    expect(calls[0].method).toBe("POST");
    expect(calls[0].url.pathname).toBe("/api/v1/reviews/abc/grade");
    expect(calls[0].url.search).toBe("?source=queue");
    expect(calls[0].headers.get("Content-Type")).toBe("application/json");
    expect(JSON.parse(calls[0].body)).toEqual({ grade: 4 });
  });

  it.each([
    ["PATCH", PATCH],
    ["DELETE", DELETE],
  ])("forwards a %s too", async (method, handler) => {
    const calls = stubFastApi(() => new Response(null, { status: 204 }));

    const response = await handler(
      apiRequest("/api/v1/events/e1", { method, access: accessTokenExpiringIn(600) }),
    );

    expect(calls[0].method).toBe(method);
    expect(response.status).toBe(204);
  });

  it("passes FastAPI's status, error body and request ID back unchanged", async () => {
    stubFastApi(() => {
      const response = apiError(422, "validation_error");
      response.headers.set("X-Request-ID", "req-42");
      return response;
    });

    const response = await POST(
      apiRequest("/api/v1/events", { method: "POST", access: accessTokenExpiringIn(600), body: "{}" }),
    );

    expect(response.status).toBe(422);
    expect(response.headers.get("Content-Type")).toContain("application/json");
    expect(response.headers.get("X-Request-ID")).toBe("req-42");
    expect((await response.json()).error.code).toBe("validation_error");
  });

  it.each([
    ["missing", undefined],
    ["under 2 minutes from expiring", accessTokenExpiringIn(60)],
  ])("answers 401 without calling FastAPI when the access token is %s", async (_, access) => {
    const calls = stubFastApi(() => Response.json({}));

    const response = await GET(apiRequest("/api/v1/events/active", { access }));

    expect(calls).toHaveLength(0);
    expect(response.status).toBe(401);
    expect((await response.json()).error.code).toBe("session_refresh_needed");
  });

  it.each(["/api/v1/auth/login", "/api/v1/auth/refresh", "/api/v1/auth/register", "/api/v1/auth/logout"])(
    "refuses %s, whose tokens must never reach browser code",
    async (path) => {
      const calls = stubFastApi(() => Response.json({}));

      const response = await POST(
        apiRequest(path, { method: "POST", access: accessTokenExpiringIn(600), body: "{}" }),
      );

      expect(calls).toHaveLength(0);
      expect(response.status).toBe(404);
    },
  );

  it("still forwards /auth/me, which returns only the profile", async () => {
    const calls = stubFastApi(() => Response.json({ email: "ana@example.com" }));

    const response = await GET(apiRequest("/api/v1/auth/me", { access: accessTokenExpiringIn(600) }));

    expect(calls).toHaveLength(1);
    expect(response.status).toBe(200);
  });

  it("answers 502 when FastAPI can't be reached", async () => {
    stubFastApi(() => {
      throw new TypeError("fetch failed");
    });

    const response = await GET(apiRequest("/api/v1/events/active", { access: accessTokenExpiringIn(600) }));

    expect(response.status).toBe(502);
  });
});
