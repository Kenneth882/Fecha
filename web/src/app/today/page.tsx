import type { Metadata } from "next";
import Link from "next/link";

import { AppHeader, Screen } from "@/components/app-header";
import { TaskRow } from "@/components/task-row";
import { ApiUnavailableError, pageApi, requireActiveEvent } from "@/lib/events/server";
import { todayHeadline } from "@/lib/events/today-headline";

export const metadata: Metadata = { title: "Today · CramPlan" };

/** "Day N of M", the countdown, today's Tasks and the Review Queue, for the Active Event. */
export default async function TodayPage() {
  const event = await requireActiveEvent("/today");
  const api = await pageApi("/today");
  const params = { params: { path: { event_id: event.id } } };
  const [today, queue] = await Promise.all([
    api.GET("/api/v1/events/{event_id}/today", params),
    api.GET("/api/v1/events/{event_id}/reviews/due", params),
  ]);
  if (!today.data || !queue.data) throw new ApiUnavailableError();

  const headline = todayHeadline(today.data);
  return (
    <>
      <AppHeader current="today" />
      <Screen>
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-semibold tracking-tight" data-testid="today-title">
            {headline.title}
          </h1>
          {headline.countdown && <p className="opacity-80">{headline.countdown}</p>}
        </div>

        {headline.message ? (
          <div className="flex flex-col gap-3 rounded-lg bg-current/5 px-4 py-4">
            <p>{headline.message}</p>
            {today.data.state === "past" && (
              <Link href="/onboarding" className="self-start font-medium text-blue-700 underline dark:text-blue-400">
                Set up your next Event
              </Link>
            )}
          </div>
        ) : (
          <>
            <section
              aria-labelledby="reviews-heading"
              className="flex items-center justify-between gap-4 rounded-lg border border-current/15 px-4 py-3"
            >
              <div>
                <h2 id="reviews-heading" className="font-medium">
                  Review Queue
                </h2>
                <p className="text-sm opacity-75">
                  {queue.data.count === 0 ? "Nothing to review right now." : "Phrases due for a quick recall."}
                </p>
              </div>
              <span className="text-2xl font-semibold tabular-nums" data-testid="review-count">
                {queue.data.count}
                <span className="sr-only"> due</span>
              </span>
            </section>

            <section aria-labelledby="tasks-heading" className="flex flex-col gap-2">
              <h2 id="tasks-heading" className="text-sm font-medium opacity-75">
                Today&apos;s Tasks
              </h2>
              <ol className="flex flex-col gap-2">
                {today.data.tasks.map((task) => (
                  <li key={task.id}>
                    <TaskRow task={task} heading={task.scenario_title} />
                  </li>
                ))}
              </ol>
            </section>
          </>
        )}
      </Screen>
    </>
  );
}
