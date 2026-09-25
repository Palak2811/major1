"use client";

import Link from "next/link";
import { use } from "react";
import { PatternDisclaimer, SkillWeightBar } from "@/components/company";
import { QuestionTable } from "@/components/QuestionTable";
import { Badge, Card, CardHeader, DifficultyBadge, ErrorState, PageHeader, Skeleton, TopicTag } from "@/components/ui";
import type { Company } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export default function CompanyDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { data: c, error, reload } = useApi<Company>(`/companies/${slug}`);

  if (error) return <ErrorState message={error.status === 404 ? "Company not found" : error.message} onRetry={reload} />;
  if (!c) return <div className="space-y-4"><Skeleton className="h-6 w-40" /><Skeleton className="h-40 w-full" /></div>;

  return (
    <div className="space-y-5">
      <div className="text-xs text-muted"><Link href="/companies" className="hover:text-text">Companies</Link> / {c.name}</div>
      <PageHeader title={c.name} description={c.description} />
      <PatternDisclaimer text={c.pattern_disclaimer} />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Online assessment pattern" description="Observed, not official." actions={<Badge tone="warn">Observed</Badge>} />
          <dl className="tabular grid grid-cols-2 gap-px bg-border sm:grid-cols-4">
            {[["Coding questions", c.oa_pattern.coding_questions], ["MCQs", c.oa_pattern.mcqs], ["Duration", `${c.oa_pattern.duration_minutes} min`]].map(([k, v]) => (
              <div key={k} className="bg-surface px-4 py-3"><dt className="text-2xs uppercase tracking-wide text-muted">{k}</dt><dd className="mt-1 text-lg font-semibold">{v}</dd></div>
            ))}
            <div className="bg-surface px-4 py-3"><dt className="text-2xs uppercase tracking-wide text-muted">Difficulty</dt><dd className="mt-1.5"><DifficultyBadge level={c.oa_pattern.difficulty} /></dd></div>
          </dl>
          <div className="p-4">
            <div className="mb-2 text-xs font-medium text-text-2">Frequently tested topics</div>
            <div className="flex flex-wrap gap-1.5">{c.oa_pattern.frequent_topics.length ? c.oa_pattern.frequent_topics.map((t) => <TopicTag key={t} name={t} />) : <span className="text-xs text-muted">None recorded</span>}</div>
          </div>
        </Card>
        <Card>
          <CardHeader title="Expected skill distribution" description="Observed emphasis across areas, in percent." />
          <div className="p-4"><SkillWeightBar weights={c.skill_weights} /></div>
          {c.readiness_weights && (
            <div className="border-t border-border p-4 text-xs text-muted">
              This company uses custom readiness weights (applied from Phase 3).
            </div>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Tagged questions" description={`${c.question_count} question(s) linked to ${c.name}`} />
        <QuestionTable filter={`company_id=${c.id}`} emptyText="Nothing is tagged with this company yet." />
      </Card>
    </div>
  );
}
