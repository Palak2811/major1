"use client";

import Link from "next/link";
import { use } from "react";
import { ReadinessReportView } from "@/components/ReadinessReportView";
import { ErrorState, PageHeader, Skeleton } from "@/components/ui";
import type { ReadinessReport } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export default function CompanyReadinessPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { data, error, reload } = useApi<ReadinessReport>(`/me/readiness?company=${encodeURIComponent(slug)}`);

  if (error) return <ErrorState message={error.status === 404 ? "Company not found" : error.message} onRetry={reload} />;
  return (
    <div>
      <div className="text-xs text-muted"><Link href="/readiness" className="hover:text-text">Readiness</Link> / {data?.company?.name ?? "…"}</div>
      <PageHeader title={data?.company ? `${data.company.name} readiness report` : "Readiness report"}
        description={data?.company ? <Link href={`/companies/${data.company.slug}`} className="text-accent hover:underline">View the observed assessment pattern</Link> : undefined} />
      {data ? <ReadinessReportView r={data} /> : <div className="space-y-4"><Skeleton className="h-40 w-full" /><Skeleton className="h-64 w-full" /></div>}
    </div>
  );
}
