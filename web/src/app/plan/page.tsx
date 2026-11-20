import type { Metadata } from "next";

import { AppHeader, Screen } from "@/components/app-header";
import { TaskRow } from "@/components/task-row";
import { DIFFICULTIES, EVENT_TYPES, formatDate } from "@/lib/events/labels";
import { ApiUnavailableError, pageApi, requireActiveEvent } from "@/lib/events/server";

export const metadata: Metadata = { title: "Plan · CramPlan" };

/**
 * The Current Plan as a read-only road: each Milestone (Scenario title, difficulty,
 * target date) with its Plan Days and Tasks, ending at the Event Day.
 */
export default async function PlanPage() {
  const api = await pageApi("/plan");
  const event = await requireActiveEvent(api);
  const { data: plan } = await api.GET("/api/v1/events/{event_id}/plan", {
    params: { path: { event_id: event.id } },
  });
  if (!plan) throw new ApiUnavailableError();

  return (
    <>
      <AppHeader current="plan" />
      <Screen>
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Your Plan</h1>
          <p className="opacity-80">
            {EVENT_TYPES[event.type].label} in Spanish on {formatDate(event.event_day, { year: true })}
          </p>
        </div>

        <ol className="flex flex-col">
          {plan.milestones.map((milestone) => (
            <li key={milestone.position} className="relative flex gap-4 pb-8">
              <RoadMarker label={String(milestone.position)} />
              <div className="flex min-w-0 flex-1 flex-col gap-3">
                <div>
                  <h2 className="font-semibold">{milestone.title}</h2>
                  <p className="text-sm opacity-75">
                    {DIFFICULTIES[milestone.difficulty] ?? `Difficulty ${milestone.difficulty}`} · ready by{" "}
                    {formatDate(milestone.target_date)}
                  </p>
                </div>
                {milestone.days.map((day) => (
                  <div key={day.date} className="flex flex-col gap-1.5">
                    <h3 className="text-xs font-medium uppercase tracking-wide opacity-60">{formatDate(day.date)}</h3>
                    <ul className="flex flex-col gap-1.5">
                      {day.tasks.map((task) => (
                        <li key={task.id}>
                          <TaskRow task={task} linked={false} />
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </li>
          ))}
          <li className="relative flex gap-4">
            <RoadMarker label="★" last />
            <div>
              <h2 className="font-semibold">Event Day</h2>
              <p className="text-sm opacity-75">{formatDate(event.event_day, { year: true })}</p>
            </div>
          </li>
        </ol>
      </Screen>
    </>
  );
}

/** A numbered stop on the road, with the line on to the next one. */
function RoadMarker({ label, last = false }: { label: string; last?: boolean }) {
  return (
    <div className="flex flex-col items-center" aria-hidden="true">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-blue-700 text-sm font-semibold text-white">
        {label}
      </span>
      {!last && <span className="w-0.5 flex-1 bg-blue-700/25" />}
    </div>
  );
}
