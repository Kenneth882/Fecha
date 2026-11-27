import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AppHeader, Screen } from "@/components/app-header";
import { activeEvent } from "@/lib/events/active-event";
import { ApiUnavailableError, loadEvents, pageApi } from "@/lib/events/server";

import { ListenQuestions } from "./listen-questions";

export const metadata: Metadata = { title: "Listen Task · CramPlan" };

/**
 * A Listen Task: its Listen Dialogue as text, then its three Comprehension Questions.
 * Opening it fixes the dialogue, so it's the same every time. Questions answered
 * before show their answers; a Task that can't be answered today is read-only. A Past
 * Event's Task still shows its dialogue, so this page doesn't need an Active Event.
 */
export default async function ListenTaskPage(props: PageProps<"/tasks/[taskId]/listen">) {
  const { taskId } = await props.params;
  const api = await pageApi(`/tasks/${taskId}/listen`);
  const [events, listen] = await Promise.all([
    loadEvents(api),
    api.GET("/api/v1/tasks/{task_id}/listen", { params: { path: { task_id: taskId } } }),
  ]);
  // 404: no such Task (or another User's); 422: not a Task ID; 409: not a Listen Task.
  if ([404, 409, 422].includes(listen.response.status)) notFound();
  if (!listen.data) throw new ApiUnavailableError();

  const event = activeEvent(events);
  const plan = event
    ? await api.GET("/api/v1/events/{event_id}/plan", { params: { path: { event_id: event.id } } })
    : null;
  if (plan && !plan.data) throw new ApiUnavailableError();
  // Not in the Active Event's Current Plan, so it's part of a Past Event.
  const milestone = plan?.data?.milestones.find((m) =>
    m.days.some((day) => day.tasks.some(({ id }) => id === taskId)),
  );
  const task = listen.data;

  return (
    <>
      <AppHeader />
      <Screen>
        <div className="flex flex-col gap-1">
          <Link href="/today" className="self-start text-sm text-blue-700 underline dark:text-blue-400">
            ← Today
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight">{milestone?.title ?? "Listen Task"}</h1>
          <p className="opacity-80">Read the conversation, then answer the three questions about it.</p>
        </div>

        <section aria-labelledby="dialogue-heading" className="flex flex-col gap-2">
          <h2 id="dialogue-heading" className="text-sm font-medium opacity-75">
            Conversation between {task.speakers.join(" and ")}
          </h2>
          <ol
            lang={milestone ? event?.target_language : undefined}
            className="flex flex-col divide-y divide-current/10 rounded-lg border border-current/15"
            data-testid="listen-lines"
          >
            {task.lines.map((line, index) => (
              <li key={index} className="flex flex-col gap-0.5 px-4 py-3">
                <span className="text-sm font-medium opacity-75">{line.speaker}</span>
                <span className="text-lg">{line.text}</span>
              </li>
            ))}
          </ol>
        </section>

        <ListenQuestions task={task} pastEvent={!milestone} />
      </Screen>
    </>
  );
}
