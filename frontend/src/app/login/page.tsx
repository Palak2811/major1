"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthLayout, Divider, GoogleButton } from "@/components/AuthLayout";
import { Button, ErrorState, Field, Input } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/useApi";

const OAUTH_ERRORS: Record<string, string> = {
  oauth_state: "Google sign-in expired or was tampered with. Please try again.",
  email_unverified: "Your Google email is not verified.",
  disabled: "This account has been disabled.",
};

function LoginForm() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const providers = useApi<{ google: { mock: boolean } }>("/auth/providers");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(OAUTH_ERRORS[params.get("error") ?? ""] ?? null);

  useEffect(() => { if (!loading && user) router.replace("/dashboard"); }, [user, loading, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Sign in" subtitle="Pick up where you left off.">
      <GoogleButton mock={providers.data?.google.mock ?? false} />
      <Divider />
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorState message={error} />}
        <Field label="Email" htmlFor="email">
          <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password" htmlFor="password">
          <Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <Button type="submit" className="w-full" loading={busy}>Sign in</Button>
      </form>
      <p className="mt-6 text-sm text-muted">
        New here? <Link href="/register" className="font-medium text-accent hover:underline">Create an account</Link>
      </p>
    </AuthLayout>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
