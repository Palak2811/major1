"use client";

import { CompanyCard, PatternDisclaimer } from "@/components/company";
import { Card, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import type { Company } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export default function CompaniesPage() {
  const { data, error, loading, reload } = useApi<Company[]>("/companies");
  return (
    <div>
      <PageHeader title="Companies" description="How each company has historically assessed candidates." />
      {data?.[0] && <div className="mb-4"><PatternDisclaimer text={data[0].pattern_disclaimer} /></div>}
      {error && <ErrorState message={error.message} onRetry={reload} />}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loading && Array.from({ length: 3 }).map((_, i) => <Card key={i} className="space-y-3 p-4"><Skeleton className="h-4 w-24" /><Skeleton className="h-12 w-full" /><Skeleton className="h-2 w-full" /></Card>)}
        {data?.map((c) => <CompanyCard key={c.id} c={c} />)}
      </div>
      {data && data.length === 0 && <Card><EmptyState title="No companies yet" description="A content manager needs to add company profiles." /></Card>}
    </div>
  );
}
