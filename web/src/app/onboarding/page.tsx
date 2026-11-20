import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AppHeader, Screen } from "@/components/app-header";
import { activeEvent } from "@/lib/events/active-event";
import { eventDayRange } from "@/lib/events/event-day-range";
import { EVENT_TYPES, formatDate } from "@/lib/events/labels";
import { ApiUnavailableError, loadEvents, pageApi } from "@/lib/events/server";

import { OnboardingForm } from "./onboarding-form";

export const metadata: Metadata = { title: "Set up your Event · CramPlan" };

/** Creating the User's Event. A User who already has an Active Event goes to Today. */
export default async function OnboardingPage() {
  const api = await pageApi("/onboarding");
  const [events, me] = await Promise.all([loadEvents("/onboarding"), api.GET("/api/v1/auth/me")]);
  if (activeEvent(events)) redirect("/today");
  if (!me.data) throw new ApiUnavailableError();

  // The Event Day's range is counted from the User's local today, as FastAPI does.
  const range = eventDayRange(new Date(), me.data.timezone);
  const lastEvent = events[0];

  return (
    <>
      <AppHeader current="onboarding" />
      <Screen>
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">Set up your Event</h1>
          <p className="opacity-80">
            Tell us what you&apos;re preparing for and when. You&apos;ll get a day-by-day Plan right away.
          </p>
        </div>
        {lastEvent && (
          <p className="rounded-md bg-current/5 px-3 py-2 text-sm">
            Your {EVENT_TYPES[lastEvent.type].label.toLowerCase()} on{" "}
            {formatDate(lastEvent.event_day, { year: true })} is over. Set up your next one below.
          </p>
        )}
        <OnboardingForm range={range} />
      </Screen>
    </>
  );
}
