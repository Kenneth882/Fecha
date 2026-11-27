import type { components } from "@/lib/api/schema";

type Task = Pick<components["schemas"]["TodayTask"], "id" | "kind">;

/** The Task's screen, or null for a Speak Task, which is locked ("Coming soon") until Week 5. */
export function taskHref(task: Task): string | null {
  switch (task.kind) {
    case "vocab":
      return `/tasks/${task.id}`;
    case "listen":
      return `/tasks/${task.id}/listen`;
    case "speak":
      return null;
  }
}
