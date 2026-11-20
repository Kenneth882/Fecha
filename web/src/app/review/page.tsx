import type { Metadata } from "next";
import Link from "next/link";

import { AppHeader, Screen } from "@/components/app-header";
import { ApiUnavailableError, pageApi, requireActiveEvent } from "@/lib/events/server";

import { ReviewSession } from "./review-session";

export const metadata: Metadata = { title: "Review · CramPlan" };

/** A Review session over the Active Event's Review Queue, as it is when the page loads. */
export default async function ReviewPage() {
  const api = await pageApi("/review");
  const event = await requireActiveEvent(api);
  const { data: queue } = await api.GET("/api/v1/events/{event_id}/reviews/due", {
    params: { path: { event_id: event.id } },
  });
  if (!queue) throw new ApiUnavailableError();

  return (
    <>
      <AppHeader />
      <Screen>
        {queue.items.length === 0 ? (
          <div className="flex flex-col gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">Nothing to review</h1>
            <p className="opacity-80">
              Your Review Queue is empty. A Vocab Task&apos;s phrases come up for Review the day after you complete it.
            </p>
            <Link href="/today" className="self-start font-medium text-blue-700 underline dark:text-blue-400">
              Back to Today
            </Link>
          </div>
        ) : (
          <ReviewSession eventId={event.id} language={event.target_language} items={queue.items} />
        )}
      </Screen>
    </>
  );
}
