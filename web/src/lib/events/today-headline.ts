import type { components } from "@/lib/api/schema";

type TodayDetail = components["schemas"]["TodayDetail"];

export type TodayHeadline = {
  title: string;
  /** Null when there's no countdown left: on the Event Day and for a Past Event. */
  countdown: string | null;
  /** Shown instead of the Tasks, when there's no Plan Day today. */
  message: string | null;
};

/** The top of Today: "Day N of M" and the countdown, or the Event Day / Past Event message. */
export function todayHeadline(today: TodayDetail): TodayHeadline {
  if (today.state === "event_day") {
    return {
      title: "It's your Event Day",
      countdown: null,
      message: "No Tasks today: you've done the work. ¡Mucha suerte!",
    };
  }
  if (today.state === "past" || today.plan_day === null) {
    return {
      title: "This Event is over",
      countdown: null,
      message: "Its Plan is finished. Set up your next Event to start a new one.",
    };
  }
  const days = today.days_until_event_day;
  return {
    title: `Day ${today.plan_day} of ${today.plan_days}`,
    countdown: days === 1 ? "Your Event Day is tomorrow" : `${days} days until your Event Day`,
    message: null,
  };
}
