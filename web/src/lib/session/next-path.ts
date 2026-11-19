const PROBE_ORIGIN = "http://cramplan.invalid";

/** Steps of logging in, which would loop if a User were sent back to them. */
const SESSION_STEPS = ["/login", "/register", "/api/session/"];

/**
 * The path to send a User to after logging in or refreshing, from a `next` parameter.
 * Only a path on this app is kept: anything that could point off-site (`//host`,
 * `/\host`, a scheme), carries control characters, or leads back into the session
 * steps becomes `/`, so `next` can never be an open redirect.
 */
export function safeNextPath(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || /[\\\s]/.test(next)) {
    return "/";
  }
  if (hasControlCharacters(next)) return "/";

  const url = new URL(next, PROBE_ORIGIN);
  if (url.origin !== PROBE_ORIGIN) return "/";
  if (SESSION_STEPS.some((step) => url.pathname === step || url.pathname.startsWith(step))) {
    return "/";
  }
  return url.pathname + url.search + url.hash;
}

function hasControlCharacters(value: string): boolean {
  try {
    return /[\u0000-\u001f\u007f]/.test(decodeURIComponent(value));
  } catch {
    return true; // Malformed percent-encoding.
  }
}
