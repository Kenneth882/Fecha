import createClient from "openapi-fetch";

import type { paths } from "./schema";

/**
 * A typed client for FastAPI, for server-side code only (Server Components, route
 * handlers). Browser code never calls FastAPI: it will call this app's own `/api/v1`,
 * which the Next.js server proxies (ADR 0007; the proxy lands in #47).
 *
 * The types in ./schema.ts are generated from the API's OpenAPI schema by
 * `npm run generate:api`; never edit them by hand.
 */
export function createApiClient() {
  return createClient<paths>({ baseUrl: apiUrl() });
}

/** FastAPI's address, e.g. `http://api:8000` in compose. Never exposed to the browser. */
function apiUrl(): string {
  const url = process.env.API_URL;
  if (!url) {
    throw new Error("API_URL is not set: point it at the FastAPI server, e.g. http://localhost:8000");
  }
  return url;
}
