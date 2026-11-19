import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiError, setCookies, stubFastApi, tokens } from "@/test/fastapi";

import { POST } from "./route";

function login(origin = "http://localhost:3000"): NextRequest {
  return new NextRequest(`${origin}/api/session/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: origin },
    body: JSON.stringify({ email: "ana@example.com", password: "s3cret-Password" }),
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("POST /api/session/login", () => {
  it("logs in through FastAPI with the submitted email and password", async () => {
    const calls = stubFastApi(() => Response.json(tokens()));

    await POST(login());

    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url.pathname).toBe("/api/v1/auth/login");
    expect(JSON.parse(calls[0].body)).toEqual({
      email: "ana@example.com",
      password: "s3cret-Password",
    });
  });

  it("keeps the access token in an httpOnly cookie for the whole app, as long as it lives", async () => {
    stubFastApi(() => Response.json(tokens({ access_token: "access-jwt", expires_in: 1800 })));

    const access = setCookies(await POST(login())).get("cramplan_access");

    expect(access?.get("value")).toBe("access-jwt");
    expect(access?.get("httponly")).toBe("true");
    expect(access?.get("samesite")).toBe("lax");
    expect(access?.get("path")).toBe("/");
    expect(access?.get("max-age")).toBe("1800");
  });

  it("sends the refresh cookie only to the session handlers, for the refresh token's lifetime", async () => {
    stubFastApi(() =>
      Response.json(tokens({ refresh_token: "refresh-token", refresh_expires_in: 2592000 })),
    );

    const refresh = setCookies(await POST(login())).get("cramplan_refresh");

    expect(refresh?.get("value")).toBe("refresh-token");
    expect(refresh?.get("httponly")).toBe("true");
    expect(refresh?.get("samesite")).toBe("lax");
    expect(refresh?.get("path")).toBe("/api/session");
    expect(refresh?.get("max-age")).toBe("2592000");
  });

  it("leaves Secure off on localhost, which is served over plain HTTP", async () => {
    stubFastApi(() => Response.json(tokens()));

    const cookies = setCookies(await POST(login("http://localhost:3000")));

    expect(cookies.get("cramplan_access")?.has("secure")).toBe(false);
    expect(cookies.get("cramplan_refresh")?.has("secure")).toBe(false);
  });

  it("marks both cookies Secure anywhere else", async () => {
    stubFastApi(() => Response.json(tokens()));

    const cookies = setCookies(await POST(login("https://cramplan.example")));

    expect(cookies.get("cramplan_access")?.get("secure")).toBe("true");
    expect(cookies.get("cramplan_refresh")?.get("secure")).toBe("true");
  });

  it("never puts a token in the response body", async () => {
    stubFastApi(() => Response.json(tokens({ access_token: "access-jwt", refresh_token: "refresh-token" })));

    const body = await (await POST(login())).text();

    expect(body).not.toContain("access-jwt");
    expect(body).not.toContain("refresh-token");
  });

  it("passes a wrong password's 401 and error body through, setting no cookies", async () => {
    stubFastApi(() => apiError(401, "invalid_credentials"));

    const response = await POST(login());

    expect(response.status).toBe(401);
    expect((await response.json()).error.code).toBe("invalid_credentials");
    expect(response.headers.getSetCookie()).toEqual([]);
  });

  it("answers 502 when FastAPI can't be reached", async () => {
    stubFastApi(() => {
      throw new TypeError("fetch failed");
    });

    const response = await POST(login());

    expect(response.status).toBe(502);
    expect((await response.json()).error.code).toBe("api_unreachable");
  });
});

describe("POST /api/session/login, behind the standalone server", () => {
  it("decides Secure from the Host header, not the 0.0.0.0 bind address", async () => {
    stubFastApi(() => Response.json(tokens()));
    const request = new NextRequest("http://0.0.0.0:3000/api/session/login", {
      method: "POST",
      headers: { Host: "localhost:3000", Origin: "http://localhost:3000" },
      body: JSON.stringify({ email: "ana@example.com", password: "s3cret-Password" }),
    });

    const cookies = setCookies(await POST(request));

    expect(cookies.get("cramplan_access")?.has("secure")).toBe(false);
  });
});
