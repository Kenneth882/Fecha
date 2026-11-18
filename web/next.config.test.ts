import { describe, expect, it } from "vitest";

import nextConfig from "./next.config";

describe("next.config headers", () => {
  it("sends the frame, nosniff and referrer headers on every path", async () => {
    const rules = (await nextConfig.headers?.()) ?? [];
    const everyPath = rules.find((rule) => rule.source === "/:path*");

    expect(Object.fromEntries(everyPath?.headers.map((h) => [h.key, h.value]) ?? [])).toEqual({
      "X-Frame-Options": "DENY",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "strict-origin-when-cross-origin",
    });
  });
});
