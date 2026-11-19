import type { Metadata } from "next";

import { AuthCard } from "@/components/auth-form";

import { RegisterForm } from "./register-form";

export const metadata: Metadata = { title: "Create an account · CramPlan" };

export default function RegisterPage() {
  return (
    <AuthCard title="Create your account">
      <RegisterForm />
    </AuthCard>
  );
}
