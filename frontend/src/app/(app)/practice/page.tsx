"use client";

import Link from "next/link";
import { useMemo } from "react";
import { Badge, Card, DifficultyBadge, EmptyState, ErrorState, PageHeader, SkeletonRows, Table, Td, Th, TopicTag } from "@/components/ui";
import type { SubmissionView } from "@/lib/judge";
import type { Page, Question } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export default function PracticeList() {
  const coding = useApi<Page<Question>>("/questions?type=coding&page_size=100");
  const sql = useApi<Page<Question>>("/questions?type=sql&page_size=100");
  const subs = useApi<SubmissionView[]>("/submissions?mode=submit&limit=100");

  const status = useMemo(() => {
    const m = new Map<number, "solved" | "attempted">();
    (subs.data ?? []).forEach((s) => {
      if (!s.verdict?.done) return;
      if (s.verdict.status === "accepted") m.set(s.question_id, "solved");
      else if (!m.has(s.question_id)) m.set(s.question_id, "attempted");
    });
    return m;
  }, [subs.data]);

  const rows = [...(coding.data?.items ?? []), ...(sql.data?.items ?? [])];
  const loading = coding.loading || sql.loading;
  const solved = rows.filter((q) => status.get(q.id) === "solved").length;

  return (
    <div>
      <PageHeader title="Coding practice"
        description="Write code in the editor, run it on samples, and submit for a Judge0 verdict on hidden tests. Accepted submissions raise your skill mastery and coding readiness."
        actions={rows.length ? <span className="tabular text-sm text-text-2">{solved} / {rows.length} solved</span> : undefined} />
      {(coding.error || sql.error) && <ErrorState message={(coding.error ?? sql.error)!.message} onRetry={() => { coding.reload(); sql.reload(); }} />}
      <Card>
        {loading && !rows.length ? <SkeletonRows rows={5} cols={4} /> : rows.length === 0 ? <EmptyState title="No coding problems yet" /> : (
          <Table>
            <thead><tr><Th className="w-24">Status</Th><Th>Problem</Th><Th>Kind</Th><Th>Difficulty</Th><Th>Topic</Th></tr></thead>
            <tbody>
              {rows.map((q) => {
                const st = status.get(q.id);
                return (
                  <tr key={q.id} className="hover:bg-surface-2/60">
                    <Td>{st === "solved" ? <Badge tone="ok">✓ Solved</Badge> : st === "attempted" ? <Badge tone="warn">Attempted</Badge> : <span className="text-xs text-muted">—</span>}</Td>
                    <Td><Link href={`/practice/${q.id}`} className="font-medium hover:text-accent">{q.title}</Link></Td>
                    <Td className="text-xs text-text-2">{q.type === "sql" ? "SQL" : "Code"}</Td>
                    <Td><DifficultyBadge level={q.difficulty} /></Td>
                    <Td>{q.topic ? <TopicTag name={q.topic.name} /> : null}</Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
