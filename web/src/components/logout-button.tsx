"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Ends the session on the server too (POST /api/session/logout), then goes to login.
 * The cookies are always cleared, but if the server couldn't be reached to end the
 * session, the User is told so instead of believing it's over everywhere.
 */
export function LogoutButton() {
  const [state, setState] = useState<"idle" | "pending" | "not-revoked">("idle");
  const router = useRouter();

  async function logOut() {
    setState("pending");
    const response = await fetch("/api/session/logout", { method: "POST" }).catch(() => null);
    if (response?.ok) {
      router.replace("/login");
      router.refresh();
      return;
    }
    setState("not-revoked");
  }

  if (state === "not-revoked") {
    return (
      <p role="alert" className="rounded-md bg-amber-500/15 px-3 py-2 text-sm">
        You&apos;re logged out on this device, but CramPlan couldn&apos;t be reached to end the
        session on the server. Log in and out again once it&apos;s back to make sure.{" "}
        <Link href="/login" className="font-medium underline">
          Go to login
        </Link>
      </p>
    );
  }

  return (
    <button
      type="button"
      onClick={logOut}
      disabled={state === "pending"}
      className="self-start rounded-md border border-current/25 px-3 py-1.5 text-sm disabled:opacity-60"
    >
      {state === "pending" ? "Logging out…" : "Log out"}
    </button>
  );
}
