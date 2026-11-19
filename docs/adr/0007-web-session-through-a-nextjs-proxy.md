# Web sessions go through a Next.js proxy, with httpOnly cookies and rotating refresh tokens

The browser never holds a token where JavaScript can read it. The web app's Next.js server proxies `/api/v1/*` to FastAPI. It keeps the access JWT and a refresh token in `HttpOnly`, `Secure`, `SameSite=Lax` cookies, and copies the access token into an `Authorization: Bearer` header on the way through. That way FastAPI's auth stays plain Bearer JWT, with no CORS and no cookie handling, and an XSS bug can't steal a session. The proxy also rejects any `POST`, `PATCH` or `DELETE` whose `Origin` isn't the app's own, which together with `SameSite=Lax` blocks CSRF.

Access tokens stay short-lived (30 minutes) so they never need revoking. Users stay logged in through a refresh token instead:
- It's random, stored hashed in Postgres, and rotated on every use.
- A session ends after 30 days of inactivity, with a hard cap of 90 days.
- If an old refresh token is used again, that's treated as theft, and every session for that User is revoked. Two exceptions keep real Users from being logged out everywhere by accident:
  - A token swapped by a refresh less than 30 seconds ago (`REFRESH_TOKEN_REUSE_GRACE_SECONDS`) gets a new token of its own, because two tabs or a retry racing one refresh look exactly like reuse. If its session has been logged out since, it's just refused.
  - An expired token is just refused, since it can't refresh anything.
- Logout revokes the token on the server, not just in the browser.

The proxy refreshes silently before the access token expires, so a User preparing for an Event over several weeks isn't asked to log in every 30 minutes.

## How the refresh works

The refresh cookie is scoped to `Path=/api/session`, so only the session route handlers (login, register, refresh, logout) ever receive it. No page or `/api/v1` request carries the long-lived token, so a bug that logs or forwards those requests can't leak it. Logout needs the token to revoke it, which is why the path is `/api/session` rather than `/api/session/refresh` alone. The `/api/v1` forwarder never sees the refresh token, so it can't refresh by itself. Refresh happens in two places instead:
- **Page loads:** Next.js's proxy (`src/proxy.ts`) sends a request whose access token is missing or within 2 minutes of expiring to `GET /api/session/refresh?next=<path>`. That handler rotates the tokens and redirects back, or to `/login?next=<path>` if the session is over. So a Server Component always has a live access token. Another site can make a browser load this GET, but that only rotates the User's own cookies, and `next` is always a path on this app.
- **Browser API calls:** the forwarder answers a missing or near-expiry token with 401. The browser client then calls `POST /api/session/refresh` and retries the request once. Requests that get a 401 together share one refresh.

The app's own origin, for the `Origin` check and for deciding `Secure`, comes from the `Host` header (plus `X-Forwarded-Proto`), not `request.nextUrl`. The standalone server builds `request.nextUrl` from its bind address, `0.0.0.0`.

## Considered Options

- **The browser calls FastAPI directly, with the token in `localStorage`:** the simplest option, but any XSS could read the token, and FastAPI would need CORS.
- **A long-lived access JWT (e.g. 7 days):** no refresh logic, but a stolen token works until it expires, and logout can't really end a session.
- **Server-side sessions in Redis instead of JWTs:** revocable and simple to reason about, but it replaces the Week 1 auth design and the API's Bearer contract for little gain.

## Consequences

`/auth/refresh` is a fifth public route, next to register, login and the two health checks. Anything other than the web app that calls the API (scripts, tests, a future mobile app) uses Bearer tokens directly and never sees the cookies.
