"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthLayout, Divider, GoogleButton } from "@/components/AuthLayout";
import { Button, ErrorState, Field, Input } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/useApi";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const providers = useApi<{ google: { mock: boolean } }>("/auth/providers");
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const weak = form.password.length > 0 && (form.password.length < 10 || /^[a-zA-Z]+$/.test(form.password) || /^\d+$/.test(form.password));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(form.full_name, form.email, form.password);
      router.replace("/profile?welcome=1");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Create your account" subtitle="Students get a personal skill graph from day one.">
      <GoogleButton mock={providers.data?.google.mock ?? false} />
      <Divider />
      <form onSubmit={submit} className="space-y-3">
        {error && <ErrorState message={error} />}
        <Field label="Full name" htmlFor="name">
          <Input id="name" required autoComplete="name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        </Field>
        <Field label="Email" htmlFor="email">
          <Input id="email" type="email" required autoComplete="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <Field label="Password" htmlFor="password" hint="At least 10 characters, mixing letters with digits or symbols."
          error={weak ? "At least 10 characters, mixing letters with digits or symbols." : undefined}>
          <Input id="password" type="password" required autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </Field>
        <Button type="submit" className="w-full" loading={busy} disabled={weak}>Create account</Button>
      </form>
      <p className="mt-6 text-sm text-muted">
        Already registered? <Link href="/login" className="font-medium text-accent hover:underline">Sign in</Link>
      </p>
    </AuthLayout>
  );
}
