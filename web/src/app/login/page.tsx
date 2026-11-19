import type { Metadata } from "next";

import { AuthCard } from "@/components/auth-form";
import { safeNextPath } from "@/lib/session/next-path";

import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Log in · CramPlan" };

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const { next } = await searchParams;
  return (
    <AuthCard title="Log in">
      <LoginForm next={safeNextPath(typeof next === "string" ? next : null)} />
    </AuthCard>
  );
}
