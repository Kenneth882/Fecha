import { redirect } from "next/navigation";

import { activeEvent } from "@/lib/events/active-event";
import { loadEvents } from "@/lib/events/server";

/**
 * Where login and register land. Only logged-in Users get here (src/proxy.ts): one
 * with an Active Event goes to Today, anyone else to onboarding.
 */
export default async function Home() {
  const event = activeEvent(await loadEvents("/"));
  redirect(event ? "/today" : "/onboarding");
}
