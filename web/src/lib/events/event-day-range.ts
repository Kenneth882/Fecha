/** The Event Day's allowed range, as FastAPI checks it (`EventDayOutOfRangeError`). */
export const MIN_DAYS_AHEAD = 3;
export const MAX_DAYS_AHEAD = 60;

/** ISO dates (`YYYY-MM-DD`), as an `<input type="date">` takes them. */
export type EventDayRange = { min: string; max: string };

/**
 * The Event Days a User can pick: 3 to 60 days after their local today in their
 * timezone (an IANA name), the same today FastAPI counts from.
 */
export function eventDayRange(now: Date, timezone: string): EventDayRange {
  const today = localToday(now, timezone);
  return { min: addDays(today, MIN_DAYS_AHEAD), max: addDays(today, MAX_DAYS_AHEAD) };
}

function localToday(now: Date, timezone: string): string {
  // en-CA formats dates as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", { timeZone: timezone }).format(now);
}

function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
