"use client";

import Link from "next/link";
import { ReadinessReportView } from "@/components/ReadinessReportView";
import { Card, CardHeader, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { MasteryBar } from "@/components/Mastery";
import type { CompanyReadiness, ReadinessReport } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export default function ReadinessOverview() {
  const general = useApi<ReadinessReport>("/me/readiness");
  const companies = useApi<CompanyReadiness[]>("/me/readiness/companies");

  return (
    <div className="space-y-5">
      <PageHeader title="Readiness" description="Company Readiness Score (Equation 3.1): a fixed, deterministic formula over your measured performance. No AI is involved in the number." />
      {(general.error || companies.error) && <ErrorState message={(general.error ?? companies.error)!.message} onRetry={() => { general.reload(); companies.reload(); }} />}

      <Card>
        <CardHeader title="By company" description="Your target companies (or all companies if you haven't picked any). Open one for its full report." />
        <div className="divide-y divide-border">
          {companies.loading && !companies.data ? <div className="p-4"><Skeleton className="h-10 w-full" /></div> :
            (companies.data ?? []).map((c) => (
              <Link key={c.slug} href={`/readiness/${c.slug}`} className="flex items-center gap-4 px-4 py-3 hover:bg-surface-2/60">
                <span className="w-40 text-sm font-medium">{c.name}</span>
                <MasteryBar value={c.overall} className="flex-1" />
                <span className="text-xs text-accent">Report →</span>
              </Link>
            ))}
        </div>
      </Card>

      <div>
        <h2 className="mb-3 text-sm font-semibold">General readiness (default weights)</h2>
        {general.data ? <ReadinessReportView r={general.data} /> : <Skeleton className="h-64 w-full" />}
      </div>
    </div>
  );
}
