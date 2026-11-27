import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];

/** An ISO date (`YYYY-MM-DD`) for people, e.g. "Wed, Dec 2". It's a calendar date, so UTC. */
export function formatDate(isoDate: string, options: { year?: boolean } = {}): string {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: options.year ? "numeric" : undefined,
    timeZone: "UTC",
  }).format(new Date(`${isoDate}T00:00:00Z`));
}

export const EVENT_TYPES: Record<Schemas["EventType"], { label: string; description: string }> = {
  interview: { label: "Job interview", description: "Introduce yourself, talk about your work, ask good questions." },
  relocation: { label: "Relocation", description: "Housing, paperwork, banks, doctors and the neighbours." },
  speech: { label: "Speech", description: "Give a short talk and handle the questions after it." },
};

export const LEVELS: Record<Schemas["Level"], { label: string; description: string }> = {
  A1: { label: "A1 · Beginner", description: "A few words and set phrases." },
  A2: { label: "A2 · Elementary", description: "Simple everyday exchanges, slowly." },
  B1: { label: "B1 · Intermediate", description: "Getting by on familiar topics." },
  B2: { label: "B2 · Upper intermediate", description: "Comfortable conversation, some gaps." },
  C1: { label: "C1 · Advanced", description: "Fluent, polishing for the occasion." },
};

export const TASK_KINDS: Record<Schemas["TaskKind"], string> = {
  vocab: "Vocabulary",
  listen: "Listening",
  speak: "Speaking",
};

export const TASK_STATUSES: Record<Schemas["TaskStatus"], string> = {
  pending: "To do",
  completed: "Done",
  missed: "Missed",
};

export const DIFFICULTIES: Record<number, string> = { 1: "Easy", 2: "Medium", 3: "Hard" };
