import { NextResponse, type NextRequest } from "next/server";

/**
 * The Content-Security-Policy for one response. Scripts run only with this response's
 * nonce, which Next.js reads from the request's CSP header and adds to its own scripts.
 * `connect-src 'self'`: browser code only ever calls this app's origin (ADR 0007).
 */
function contentSecurityPolicy(nonce: string): string {
  // `next dev` needs eval (React's server error stacks) and inline styles (its overlay).
  const isDev = process.env.NODE_ENV === "development";
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' ${isDev ? "'unsafe-inline'" : `'nonce-${nonce}'`}`,
    "img-src 'self' blob: data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

export function proxy(request: NextRequest): NextResponse {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const policy = contentSecurityPolicy(nonce);

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("Content-Security-Policy", policy);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  return response;
}

export const config = {
  // Everything but Next.js's hashed build assets, which don't need a policy.
  matcher: ["/((?!_next/static|_next/image).*)"],
};
