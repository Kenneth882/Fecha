import type { NextRequest } from "next/server";

/**
 * This app's origin as the browser sees it: the `Host` header the browser sent, with
 * the scheme a TLS-terminating proxy reports in `X-Forwarded-Proto`. Not
 * `request.nextUrl`, which the standalone server builds from the address it's bound
 * to (`http://0.0.0.0:3000` in compose).
 *
 * A browser always sets `Host` to the site it's talking to, so another site can't make
 * a page's request look same-origin through it.
 */
export function appOrigin(request: NextRequest): URL {
  const host = request.headers.get("Host") ?? request.nextUrl.host;
  const forwardedProto = request.headers.get("X-Forwarded-Proto")?.split(",")[0]?.trim();
  const scheme = forwardedProto === "https" || forwardedProto === "http"
    ? forwardedProto
    : request.nextUrl.protocol.replace(/:$/, "");
  return new URL(`${scheme}://${host}`);
}
