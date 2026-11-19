import createClient from "openapi-fetch";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ACCESS_COOKIE } from "@/lib/session/cookies";

import { apiUrl } from "./client";
import type { paths } from "./schema";

/**
 * The typed API client for Server Components, calling FastAPI as the logged-in User.
 * `src/proxy.ts` only renders a page with an access token that isn't about to expire,
 * so a 401 here means FastAPI refused a live-looking token (a deleted User, a rotated
 * signing key): the User is sent to login, which replaces it, and back to `currentPath`.
 *
 * `redirect()` throws, so a caller that catches errors must `unstable_rethrow` them.
 */
export async function createUserApiClient(currentPath: string) {
  const accessToken = (await cookies()).get(ACCESS_COOKIE)?.value;
  const client = createClient<paths>({
    baseUrl: apiUrl(),
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  client.use({
    onResponse({ response }) {
      if (response.status === 401) redirect(`/login?next=${encodeURIComponent(currentPath)}`);
    },
  });
  return client;
}
