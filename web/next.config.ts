import type { NextConfig } from "next";

// The Content-Security-Policy is set per request in src/proxy.ts, since it carries a
// fresh nonce. That needs every page rendered per request, so there's no
// `cacheComponents` (Partial Prerendering can't use nonces).
const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
];

const nextConfig: NextConfig = {
  // A self-contained server in .next/standalone, for a small Docker image.
  output: "standalone",
  poweredByHeader: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
