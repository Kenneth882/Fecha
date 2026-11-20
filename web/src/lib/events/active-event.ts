import type { components } from "@/lib/api/schema";

type EventSummary = components["schemas"]["EventSummary"];

/**
 * The User's Active Event among all their Events (GET /events), or null. A User has
 * at most one (ADR 0001), and it's still active on its Event Day (ADR 0005). It
 * decides where a logged-in User goes: Today if they have one, onboarding if not.
 */
export function activeEvent(events: readonly EventSummary[]): EventSummary | null {
  return events.find((event) => event.state !== "past") ?? null;
}
