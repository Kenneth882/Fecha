import Link from "next/link";

import type { components } from "@/lib/api/schema";
import { TASK_KINDS, TASK_STATUSES, isTaskLocked } from "@/lib/events/labels";

type Task = Pick<
  components["schemas"]["TodayTask"],
  "id" | "kind" | "estimated_minutes" | "vocab_batch_size" | "status"
>;

/**
 * One Task, on Today or in the Plan. A Vocab Task links to its screen when `linked`;
 * Listen and Speak Tasks are locked ("Coming soon"): shown, but not links or buttons.
 */
export function TaskRow({ task, heading, linked = true }: { task: Task; heading?: string; linked?: boolean }) {
  const locked = isTaskLocked(task.kind);
  const details = [
    TASK_KINDS[task.kind],
    task.vocab_batch_size ? `${task.vocab_batch_size} phrases` : null,
    `${task.estimated_minutes} min`,
  ]
    .filter(Boolean)
    .join(" · ");

  const body = (
    <>
      <span className="flex min-w-0 flex-col">
        {heading && <span className="truncate font-medium">{heading}</span>}
        <span className={heading ? "text-sm opacity-75" : "text-sm"}>{details}</span>
      </span>
      <StatusBadge status={task.status} locked={locked} />
    </>
  );
  const className = "flex items-center justify-between gap-3 rounded-lg border px-4 py-3";

  if (locked) {
    return (
      <div
        aria-disabled="true"
        data-testid="task-locked"
        className={`${className} border-dashed border-current/15 opacity-60`}
      >
        {body}
      </div>
    );
  }
  if (!linked) return <div className={`${className} border-current/15`}>{body}</div>;
  return (
    <Link
      href={`/tasks/${task.id}`}
      data-testid="task-link"
      className={`${className} border-current/15 hover:border-blue-600 focus-visible:border-blue-600`}
    >
      {body}
    </Link>
  );
}

function StatusBadge({ status, locked }: { status: Task["status"]; locked: boolean }) {
  const label = locked ? "Coming soon" : TASK_STATUSES[status];
  const tone = locked
    ? "bg-current/10"
    : status === "completed"
      ? "bg-green-600/15 text-green-800 dark:text-green-300"
      : status === "missed"
        ? "bg-amber-500/15 text-amber-800 dark:text-amber-300"
        : "bg-blue-600/10 text-blue-800 dark:text-blue-300";
  return (
    <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`} data-testid="task-status">
      {label}
    </span>
  );
}
