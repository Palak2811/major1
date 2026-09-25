"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { EmptyState, Skeleton } from "./ui";

/** Client-side routing guard. The API enforces the same scopes (401/403) server-side. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => { if (!loading && !user) router.replace("/login"); }, [user, loading, router]);
  if (loading || !user) {
    return (
      <div className="flex min-h-screen">
        <div className="hidden w-56 border-r border-border bg-surface p-4 md:block"><Skeleton className="h-5 w-24" /></div>
        <div className="flex-1 space-y-4 p-8"><Skeleton className="h-6 w-48" /><Skeleton className="h-32 w-full" /></div>
      </div>
    );
  }
  return <>{children}</>;
}

export function RequireScope({ scope, children }: { scope: string; children: React.ReactNode }) {
  const { can } = useAuth();
  if (!can(scope)) {
    return <EmptyState title="You don’t have access to this area" description={`This page requires the “${scope}” permission.`} />;
  }
  return <>{children}</>;
}
