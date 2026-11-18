import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

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
    const policy = csp(proxy(new NextRequest("http://localhost:3000/")));

    expect(policy.get("connect-src")).toEqual(["'self'"]);
    expect(policy.get("default-src")).toEqual(["'self'"]);
    expect(policy.get("frame-ancestors")).toEqual(["'none'"]);
    expect(policy.get("object-src")).toEqual(["'none'"]);
  });

  it("allows only scripts carrying this response's nonce, never arbitrary inline ones", () => {
    const policy = csp(proxy(new NextRequest("http://localhost:3000/")));
    const scripts = policy.get("script-src") ?? [];

    expect(scripts).toContainEqual(expect.stringMatching(/^'nonce-[A-Za-z0-9+/=]{16,}'$/));
    expect(scripts).not.toContain("'unsafe-inline'");
    expect(scripts).not.toContain("'unsafe-eval'");
  });

  it("uses a fresh nonce on every request", () => {
    const nonce = () =>
      csp(proxy(new NextRequest("http://localhost:3000/")))
        .get("script-src")
        ?.find((value) => value.startsWith("'nonce-"));

    expect(nonce()).not.toEqual(nonce());
  });
});
