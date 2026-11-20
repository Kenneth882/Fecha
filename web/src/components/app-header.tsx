import Link from "next/link";

import { LogoutButton } from "@/components/logout-button";
import { site } from "@/app/site";

const LINKS = [
  { href: "/today", label: "Today" },
  { href: "/plan", label: "Plan" },
] as const;

/**
 * The bar at the top of every logged-in screen. Onboarding has no Event yet, so it
 * shows no links. A screen without `current` (a Task, a Review session) shows them,
 * none marked current.
 */
export function AppHeader({ current }: { current?: "today" | "plan" | "onboarding" }) {
  return (
    <header className="border-b border-current/10">
      <div className="mx-auto flex w-full max-w-xl items-center gap-4 px-4 py-3">
        <span className="font-semibold tracking-tight">{site.name}</span>
        {current !== "onboarding" && (
          <nav className="flex gap-1 text-sm" aria-label="Main">
            {LINKS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                aria-current={href === `/${current}` ? "page" : undefined}
                className="rounded-md px-2.5 py-1.5 aria-[current=page]:bg-blue-700/10 aria-[current=page]:font-medium aria-[current=page]:text-blue-800 dark:aria-[current=page]:text-blue-300"
              >
                {label}
              </Link>
            ))}
          </nav>
        )}
        <div className="ml-auto">
          <LogoutButton />
        </div>
      </div>
    </header>
  );
}

/** The column every logged-in screen's content sits in, phone width first. */
export function Screen({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-6">{children}</main>;
}
