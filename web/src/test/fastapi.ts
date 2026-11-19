import { vi } from "vitest";

import type { components } from "@/lib/api/schema";

export const API_URL = "http://api.test:8000";

/**
 * Stands in for FastAPI: every `fetch` the web server makes goes to `respond`, and is
 * recorded (with its body read) for assertions. Tests never reach a real API.
 */
export function stubFastApi(respond: (request: Request) => Response | Promise<Response>) {
  const calls: { method: string; url: URL; headers: Headers; body: string }[] = [];
  vi.stubEnv("API_URL", API_URL);
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    calls.push({
      method: request.method,
      url: new URL(request.url),
      headers: request.headers,
      body: await request.clone().text(),
    });
    return respond(request);
  });
  return calls;
}

export function tokens(
  overrides: Partial<components["schemas"]["TokenResponse"]> = {},
): components["schemas"]["TokenResponse"] {
  return {
    access_token: "access-jwt",
    token_type: "bearer",
    expires_in: 1800,
    refresh_token: "refresh-token",
    refresh_expires_in: 2592000,
    ...overrides,
  };
}

export function apiError(status: number, code: string, message = code): Response {
  return Response.json({ error: { code, message, details: [], request_id: "req-1" } }, { status });
}

/** The response's `Set-Cookie` headers, parsed into name → attributes (lowercased keys). */
export function setCookies(response: Response): Map<string, Map<string, string>> {
  return new Map(
    response.headers.getSetCookie().map((header) => {
      const [pair, ...attributes] = header.split(";").map((part) => part.trim());
      const [name, value] = pair.split("=");
      const parsed = new Map<string, string>([["value", value ?? ""]]);
      for (const attribute of attributes) {
        const [key, attrValue] = attribute.split("=");
        parsed.set(key.toLowerCase(), attrValue ?? "true");
      }
      return [name, parsed];
    }),
  );
}
