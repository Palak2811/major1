"use client";

import Link from "next/link";
import { Card, CardHeader, ErrorState, PageHeader, Skeleton, Stat } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import type { Stats } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export default function AdminOverview() {
  const { data, error, reload } = useApi<Stats>("/users/stats");
  const { can } = useAuth();
  const cells: [string, keyof Stats][] = [
    ["Users", "users"], ["Students", "students"], ["Topics", "topics"],
    ["Published questions", "questions_published"], ["Draft questions", "questions_draft"], ["Companies", "companies"],
  ];
  const links = [
    { href: "/admin/questions", t: "Questions", d: "Create, edit and publish questions of all 8 types." },
    { href: "/admin/topics", t: "Topics", d: "Maintain the topic taxonomy used for tagging." },
    { href: "/admin/companies", t: "Companies", d: "Observed OA patterns and skill-weight distributions." },
    ...(can("users:manage") ? [{ href: "/admin/users", t: "Users", d: "Roles, access and account status." }] : []),
  ];
  return (
    <div className="space-y-5">
      <PageHeader title="Admin overview" description="Content and account health." />
      {error && <ErrorState message={error.message} onRetry={reload} />}
      <Card>
        <div className="grid grid-cols-2 divide-border sm:grid-cols-3 lg:grid-cols-6 lg:divide-x">
          {cells.map(([label, key]) => (
            <Stat key={key} label={label} value={data ? data[key] : <Skeleton className="mt-1 h-7 w-10" />} />
          ))}
        </div>
      </Card>
      <Card>
        <CardHeader title="Manage" />
        <div className="grid divide-y divide-border sm:grid-cols-2 sm:divide-y-0">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className="block px-4 py-3 hover:bg-surface-2">
              <div className="text-sm font-medium">{l.t}</div>
              <div className="text-xs text-muted">{l.d}</div>
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}
