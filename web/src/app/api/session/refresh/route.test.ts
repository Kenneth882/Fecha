import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiError, setCookies, stubFastApi, tokens } from "@/test/fastapi";

import { GET, POST } from "./route";

function withRefreshCookie(request: NextRequest, refreshToken?: string): NextRequest {
  if (refreshToken) request.cookies.set("cramplan_refresh", refreshToken);
  return request;
}

function postRefresh(refreshToken?: string): NextRequest {
  return withRefreshCookie(
    new NextRequest("http://localhost:3000/api/session/refresh", {
      method: "POST",
      headers: { Origin: "http://localhost:3000" },
    }),
    refreshToken,
  );
}

function getRefresh(next: string, refreshToken?: string): NextRequest {
  const url = new URL("http://localhost:3000/api/session/refresh");
  url.searchParams.set("next", next);
  return withRefreshCookie(new NextRequest(url), refreshToken);
}

function expectCleared(response: Response): void {
  const cookies = setCookies(response);
  expect(cookies.get("cramplan_access")?.get("max-age")).toBe("0");
  expect(cookies.get("cramplan_access")?.get("path")).toBe("/");
  expect(cookies.get("cramplan_refresh")?.get("max-age")).toBe("0");
  expect(cookies.get("cramplan_refresh")?.get("path")).toBe("/api/session");
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("POST /api/session/refresh", () => {
  it("swaps the refresh cookie's token at FastAPI and sets both new cookies", async () => {
    const calls = stubFastApi(() =>
      Response.json(tokens({ access_token: "new-access", refresh_token: "new-refresh" })),
    );

    const response = await POST(postRefresh("old-refresh"));

    expect(calls[0].url.pathname).toBe("/api/v1/auth/refresh");
    expect(JSON.parse(calls[0].body)).toEqual({ refresh_token: "old-refresh" });
    expect(response.status).toBe(204);
    const cookies = setCookies(response);
    expect(cookies.get("cramplan_access")?.get("value")).toBe("new-access");
    expect(cookies.get("cramplan_refresh")?.get("value")).toBe("new-refresh");
    expect(await response.text()).toBe("");
  });

  it("ends the session without calling FastAPI when there's no refresh cookie", async () => {
    const calls = stubFastApi(() => Response.json(tokens()));

    const response = await POST(postRefresh());

    expect(calls).toHaveLength(0);
    expect(response.status).toBe(401);
    expectCleared(response);
  });

  it("clears the cookies and answers 401 when FastAPI refuses the token", async () => {
    stubFastApi(() => apiError(401, "invalid_refresh_token"));

    const response = await POST(postRefresh("revoked-refresh"));

    expect(response.status).toBe(401);
    expectCleared(response);
  });

  it("keeps the cookies when FastAPI is only unreachable, so the session survives", async () => {
    stubFastApi(() => {
      throw new TypeError("fetch failed");
    });

    const response = await POST(postRefresh("old-refresh"));

    expect(response.status).toBe(502);
    expect(response.headers.getSetCookie()).toEqual([]);
  });
});

describe("GET /api/session/refresh (a page load with a stale access token)", () => {
  it("refreshes and sends the User back to the page they asked for", async () => {
    stubFastApi(() => Response.json(tokens({ access_token: "new-access" })));

    const response = await GET(getRefresh("/plan?week=2", "old-refresh"));

    expect(response.status).toBe(307);
    expect(response.headers.get("Location")).toBe("http://localhost:3000/plan?week=2");
    expect(setCookies(response).get("cramplan_access")?.get("value")).toBe("new-access");
  });

  it("sends a User whose session is over to login, keeping where they were", async () => {
    stubFastApi(() => apiError(401, "invalid_refresh_token"));

    const response = await GET(getRefresh("/plan", "expired-refresh"));

    expect(response.status).toBe(307);
    const location = new URL(response.headers.get("Location") ?? "");
    expect(location.pathname).toBe("/login");
    expect(location.searchParams.get("next")).toBe("/plan");
    expectCleared(response);
  });

  it("shows a page, not raw JSON, when FastAPI can't be reached, and keeps the session", async () => {
    stubFastApi(() => {
      throw new TypeError("fetch failed");
    });

    const response = await GET(getRefresh("/plan?week=2", "old-refresh"));

    expect(response.status).toBe(503);
    expect(response.headers.get("Content-Type")).toContain("text/html");
    expect(response.headers.get("Retry-After")).toBeTruthy();
    const html = await response.text();
    expect(html).toContain("can't be reached");
    expect(html).toContain('href="/plan?week=2"');
    expect(response.headers.getSetCookie()).toEqual([]);
  });

  it("escapes next in that page, so it can't inject markup", async () => {
    stubFastApi(() => {
      throw new TypeError("fetch failed");
    });

    const html = await (await GET(getRefresh('/plan?q="><script>x</script>', "old-refresh"))).text();

    expect(html).not.toContain("<script>");
    expect(html).toContain('href="/plan?q=%22%3E%3Cscript%3Ex%3C/script%3E"');
  });

  it("never redirects off-site, whatever next says", async () => {
    stubFastApi(() => Response.json(tokens()));

    const response = await GET(getRefresh("https://evil.example/", "old-refresh"));

    expect(response.headers.get("Location")).toBe("http://localhost:3000/");
  });
});
