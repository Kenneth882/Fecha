import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { ACCESS_COOKIE } from "@/lib/session/cookies";
import { accessTokenExpiringIn } from "@/test/tokens";

import { proxy } from "./proxy";

function csp(response: Response): Map<string, string[]> {
  const header = response.headers.get("Content-Security-Policy") ?? "";
  return new Map(
    header
      .split(";")
      .map((directive) => directive.trim().split(/\s+/))
      .filter(([name]) => name)
      .map(([name, ...values]) => [name, values]),
  );
}

describe("proxy", () => {
  it("only lets the page connect to its own origin", () => {
    const policy = csp(proxy(new NextRequest("http://localhost:3000/login")));

    expect(policy.get("connect-src")).toEqual(["'self'"]);
    expect(policy.get("default-src")).toEqual(["'self'"]);
    expect(policy.get("frame-ancestors")).toEqual(["'none'"]);
    expect(policy.get("object-src")).toEqual(["'none'"]);
  });

  it("allows only scripts carrying this response's nonce, never arbitrary inline ones", () => {
    const policy = csp(proxy(new NextRequest("http://localhost:3000/login")));
    const scripts = policy.get("script-src") ?? [];

    expect(scripts).toContainEqual(expect.stringMatching(/^'nonce-[A-Za-z0-9+/=]{16,}'$/));
    expect(scripts).not.toContain("'unsafe-inline'");
    expect(scripts).not.toContain("'unsafe-eval'");
  });

  it("uses a fresh nonce on every request", () => {
    const nonce = () =>
      csp(proxy(new NextRequest("http://localhost:3000/login")))
        .get("script-src")
        ?.find((value) => value.startsWith("'nonce-"));

    expect(nonce()).not.toEqual(nonce());
  });
});

describe("proxy: changing requests from another origin", () => {
  const changing = ["POST", "PATCH", "PUT", "DELETE"];

  it.each(changing)("rejects a cross-origin %s", (method) => {
    const response = proxy(
      new NextRequest("http://localhost:3000/api/v1/events", {
        method,
        headers: { Origin: "https://evil.example" },
      }),
    );

    expect(response.status).toBe(403);
  });

  it.each(changing)("rejects a %s that carries no Origin", (method) => {
    const response = proxy(new NextRequest("http://localhost:3000/api/v1/events", { method }));

    expect(response.status).toBe(403);
  });

  it.each(changing)("lets a same-origin %s through", (method) => {
    const response = proxy(
      new NextRequest("http://localhost:3000/api/v1/events", {
        method,
        headers: { Origin: "http://localhost:3000" },
      }),
    );

    expect(response.status).not.toBe(403);
  });

  it("always lets a GET through, whatever its Origin", () => {
    const response = proxy(
      new NextRequest("http://localhost:3000/api/v1/events", {
        headers: { Origin: "https://evil.example" },
      }),
    );

    expect(response.status).not.toBe(403);
  });
});

describe("proxy: pages need a session", () => {
  function page(path: string, accessToken?: string): NextRequest {
    const request = new NextRequest(`http://localhost:3000${path}`);
    if (accessToken) request.cookies.set(ACCESS_COOKIE, accessToken);
    return request;
  }

  it("sends a visitor with no access token through a refresh, back to the page", () => {
    const response = proxy(page("/plan?week=2"));

    expect(response.status).toBe(307);
    const location = new URL(response.headers.get("Location") ?? "");
    expect(location.pathname).toBe("/api/session/refresh");
    expect(location.searchParams.get("next")).toBe("/plan?week=2");
  });

  it("refreshes an access token with under 2 minutes left before rendering", () => {
    const response = proxy(page("/", accessTokenExpiringIn(90)));

    expect(response.status).toBe(307);
    expect(new URL(response.headers.get("Location") ?? "").pathname).toBe("/api/session/refresh");
  });

  it("renders the page for a fresh access token", () => {
    const response = proxy(page("/", accessTokenExpiringIn(600)));

    expect(response.status).toBe(200);
  });

  it("refreshes a malformed access token rather than trusting it", () => {
    const response = proxy(page("/", "not-a-jwt"));

    expect(response.status).toBe(307);
  });

  it.each(["/login", "/register", "/manifest.webmanifest", "/icons/icon-192.png", "/icon.svg"])(
    "lets %s through without a session",
    (path) => {
      expect(proxy(page(path)).status).toBe(200);
    },
  );

  it("leaves /api requests to their route handlers, which answer 401 themselves", () => {
    expect(proxy(page("/api/v1/events/active")).status).toBe(200);
  });

  it.each(["/login", "/register"])(
    "always lets %s through, even with a live-looking token FastAPI may have refused",
    (path) => {
      // Bouncing these to / would trap a User whose token FastAPI rejects (deleted
      // User, rotated signing key): / sends them to login, and login back to /.
      expect(proxy(page(path, accessTokenExpiringIn(600))).status).toBe(200);
    },
  );
});

describe("proxy: the app's own origin, behind the standalone server", () => {
  // `next start` / the standalone server bind to 0.0.0.0, and NextRequest's own URL
  // carries that address; the browser's Host header is the real origin.
  function bound(path: string, headers: Record<string, string>): NextRequest {
    return new NextRequest(`http://0.0.0.0:3000${path}`, { method: "POST", headers });
  }

  it("takes its origin from the Host header, not the address it's bound to", () => {
    const response = proxy(
      bound("/api/session/logout", { Host: "localhost:3000", Origin: "http://localhost:3000" }),
    );

    expect(response.status).not.toBe(403);
  });

  it("still rejects the bind address itself as an Origin when the Host differs", () => {
    const response = proxy(
      bound("/api/session/logout", { Host: "localhost:3000", Origin: "http://0.0.0.0:3000" }),
    );

    expect(response.status).toBe(403);
  });

  it("uses the scheme a TLS-terminating proxy reports in X-Forwarded-Proto", () => {
    const response = proxy(
      bound("/api/session/logout", {
        Host: "cramplan.example",
        "X-Forwarded-Proto": "https",
        Origin: "https://cramplan.example",
      }),
    );

    expect(response.status).not.toBe(403);
  });
});
