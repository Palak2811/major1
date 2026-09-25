"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, CardHeader, CompanyTag, EmptyState, ErrorState, PageHeader, Skeleton, SkeletonRows, Table, Td, Th } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtDate, fmtDuration } from "@/lib/format";
import type { AttemptListItem, AttemptView, TestSummary } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export default function TestsPage() {
  const router = useRouter();
  const tests = useApi<TestSummary[]>("/tests");
  const history = useApi<AttemptListItem[]>("/attempts?mode=test");
  const [starting, setStarting] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function start(t: TestSummary) {
    setStarting(t.id);
    setError(null);
    try {
      const a = await api<AttemptView>(`/tests/${t.id}/attempts`, { method: "POST" });
      router.push(`/tests/attempt/${a.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start the test");
      setStarting(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Tests" description="Timed, sectioned mock assessments. Answers save automatically; the test submits itself when time runs out." />
      {error && <ErrorState message={error} />}
      {tests.error && <ErrorState message={tests.error.message} onRetry={tests.reload} />}

      <div className="grid gap-4 md:grid-cols-2">
        {tests.loading && Array.from({ length: 2 }).map((_, i) => <Card key={i} className="space-y-3 p-4"><Skeleton className="h-4 w-40" /><Skeleton className="h-12 w-full" /></Card>)}
        {tests.data?.map((t) => (
          <Card key={t.id} className="flex flex-col p-4">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-semibold">{t.title}</h3>
              {t.company && <CompanyTag name={t.company.name} />}
            </div>
            {t.description && <p className="mt-1 text-xs text-muted">{t.description}</p>}
            <dl className="tabular mt-4 grid grid-cols-3 gap-2 text-center">
              {[["Questions", t.question_count], ["Marks", t.total_marks], ["Time", fmtDuration(t.duration_seconds * 1000)]].map(([k, v]) => (
                <div key={k} className="rounded-md bg-surface-2 py-1.5"><dd className="text-sm font-semibold">{v}</dd><dt className="text-2xs text-muted">{k}</dt></div>
              ))}
            </dl>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {t.sections.map((s) => <Badge key={s.name}>{s.name}{s.time_limit_seconds ? ` · ${Math.round(s.time_limit_seconds / 60)}m` : ""}</Badge>)}
              {t.negative_marking && <Badge tone="danger">Negative marking</Badge>}
            </div>
            <div className="mt-4 flex justify-end border-t border-border pt-3">
              <Button loading={starting === t.id} onClick={() => start(t)}>{t.active_attempt_id ? "Resume attempt" : "Start test"}</Button>
            </div>
          </Card>
        ))}
      </div>
      {tests.data?.length === 0 && <Card><EmptyState title="No tests published yet" description="Content managers can compose tests from the admin panel." /></Card>}

      <Card>
        <CardHeader title="Attempt history" />
        {history.loading && !history.data ? <SkeletonRows rows={3} cols={4} /> :
          !history.data?.length ? <EmptyState title="No attempts yet" /> : (
            <Table>
              <thead><tr><Th>Test</Th><Th>Started</Th><Th>Status</Th><Th className="text-right">Score</Th><Th /></tr></thead>
              <tbody>
                {history.data.map((a) => (
                  <tr key={a.id}>
                    <Td className="font-medium">{a.title}</Td>
                    <Td className="text-text-2">{fmtDate(a.started_at)}</Td>
                    <Td>{a.status === "in_progress" ? <Badge tone="warn">In progress</Badge> : <Badge tone="ok">Submitted</Badge>}</Td>
                    <Td className="tabular text-right">{a.score == null ? "—" : `${a.score} / ${a.max_score}`}</Td>
                    <Td className="text-right">
                      <Link href={a.status === "in_progress" ? `/tests/attempt/${a.id}` : `/tests/attempt/${a.id}/analysis`}>
                        <Button size="sm" variant="ghost">{a.status === "in_progress" ? "Resume" : "Analysis"}</Button>
                      </Link>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
      </Card>
    </div>
  );
}
