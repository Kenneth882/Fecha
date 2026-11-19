"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/** Ends the session on the server too (POST /api/session/logout), then goes to login. */
export function LogoutButton() {
  const [pending, setPending] = useState(false);
  const router = useRouter();

  async function logOut() {
    setPending(true);
    await fetch("/api/session/logout", { method: "POST" }).catch(() => null);
    router.replace("/login");
    router.refresh();
  }

  return (
    <button
      type="button"
      onClick={logOut}
      disabled={pending}
      className="self-start rounded-md border border-current/25 px-3 py-1.5 text-sm disabled:opacity-60"
    >
      {pending ? "Logging out…" : "Log out"}
    </button>
  );
}
