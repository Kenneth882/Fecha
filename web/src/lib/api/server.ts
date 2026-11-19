import createClient from "openapi-fetch";
import { cookies } from "next/headers";

import { ACCESS_COOKIE } from "@/lib/session/cookies";

import { apiUrl } from "./client";
import type { paths } from "./schema";

/**
 * The typed API client for Server Components, calling FastAPI as the logged-in User.
 * `src/proxy.ts` only renders a page with an access token that has at least 2 minutes
 * left, so the token here is always live.
 */
export async function createUserApiClient() {
  const accessToken = (await cookies()).get(ACCESS_COOKIE)?.value;
  return createClient<paths>({
    baseUrl: apiUrl(),
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
}
