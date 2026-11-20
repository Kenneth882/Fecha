import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AppHeader, Screen } from "@/components/app-header";
import { TASK_STATUSES } from "@/lib/events/labels";
import { ApiUnavailableError, pageApi, requireActiveEvent } from "@/lib/events/server";

import { DoneButton } from "./done-button";

export const metadata: Metadata = { title: "Vocab Task · CramPlan" };

/**
 * A Vocab Task: its batch of phrases with their translations, and Done, which
 * completes it (introducing the batch) and goes back to Today. A Task can be completed
 * only on its own Plan Day, so one that isn't today's pending Task is shown read-only.
 */
export default async function VocabTaskPage(props: PageProps<"/tasks/[taskId]">) {
  const { taskId } = await props.params;
  const api = await pageApi(`/tasks/${taskId}`);
  const event = await requireActiveEvent(api);
  const [today, batch] = await Promise.all([
    api.GET("/api/v1/events/{event_id}/today", { params: { path: { event_id: event.id } } }),
    api.GET("/api/v1/tasks/{task_id}/vocab", { params: { path: { task_id: taskId } } }),
  ]);
  // 404: no such Task (or another User's); 422: not a Task ID; 409: not a Vocab Task.
  if ([404, 409, 422].includes(batch.response.status)) notFound();
  if (!today.data || !batch.data) throw new ApiUnavailableError();

  const task = today.data.tasks.find(({ id }) => id === taskId);
  const items = batch.data.items;
  const completable = task?.status === "pending";

  return (
    <>
      <AppHeader />
      <Screen>
        <div className="flex flex-col gap-1">
          <Link href="/today" className="self-start text-sm text-blue-700 underline dark:text-blue-400">
            ← Today
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight">{task?.scenario_title ?? "Vocab Task"}</h1>
          <p className="opacity-80">
            {items.length === 1 ? "1 new phrase" : `${items.length} new phrases`}
            {completable ? ". Read each one aloud, then tap Done." : "."}
          </p>
        </div>

        {items.length === 0 ? (
          <p className="rounded-lg bg-current/5 px-4 py-4">
            This Scenario has no new phrases left for your level. You can still mark the Task done.
          </p>
        ) : (
          <ol className="flex flex-col divide-y divide-current/10 rounded-lg border border-current/15" data-testid="vocab-items">
            {items.map((item) => (
              <li key={item.id} className="flex flex-col gap-0.5 px-4 py-3">
                <span lang={event.target_language} className="text-lg font-medium">
                  {item.phrase}
                </span>
                <span className="opacity-75">{item.translation}</span>
              </li>
            ))}
          </ol>
        )}

        {completable ? (
          <DoneButton taskId={taskId} />
        ) : (
          <p className="rounded-md bg-current/5 px-3 py-2 text-sm" data-testid="task-readonly">
            {task
              ? `This Task is ${TASK_STATUSES[task.status].toLowerCase()}.`
              : "This Task isn't one of today's, so it can't be completed here."}
          </p>
        )}
      </Screen>
    </>
  );
}
