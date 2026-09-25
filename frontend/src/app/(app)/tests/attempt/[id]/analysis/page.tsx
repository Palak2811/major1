"use client";

import clsx from "clsx";
import Link from "next/link";
import { use, useMemo, useState } from "react";
import { AnswerInput, describeKey } from "@/components/AnswerInput";
import { QuestionView } from "@/components/QuestionView";
import { Badge, Button, Card, CardHeader, DifficultyBadge, ErrorState, Skeleton, Stat, Table, Td, Th } from "@/components/ui";
import { fmtDate, fmtDuration, pct } from "@/lib/format";
import type { Analysis, AnalysisItem, Breakdown } from "@/lib/types";
import { TYPE_LABEL } from "@/lib/types";
import { useApi } from "@/lib/useApi";

const STATUS: Record<AnalysisItem["status"], { label: string; tone: "ok" | "danger" | "neutral" | "info" }> = {
  correct: { label: "Correct", tone: "ok" },
  incorrect: { label: "Incorrect", tone: "danger" },
  unanswered: { label: "Unanswered", tone: "neutral" },
  pending: { label: "Pending judge", tone: "info" },
};

function BreakdownTable({ title, rows }: { title: string; rows: Breakdown[] }) {
  return (
    <Card>
      <CardHeader title={title} />
      <Table>
        <thead><tr><Th>{title.replace("By ", "")}</Th><Th className="text-right">Score</Th><Th className="text-right">Correct</Th><Th className="text-right">Time</Th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name}>
              <Td className="font-medium">{r.name}</Td>
              <Td className="tabular text-right">{r.awarded} / {r.max}</Td>
              <Td className="tabular text-right text-text-2">{r.correct} / {r.attempted}</Td>
              <Td className="tabular text-right text-text-2">{fmtDuration(r.time_ms)}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error, reload } = useApi<Analysis>(`/attempts/${id}/analysis`);
  const [open, setOpen] = useState<number | null>(null);
  const [filter, setFilter] = useState<"all" | AnalysisItem["status"] | "flagged">("all");

  const maxTime = useMemo(() => Math.max(1, ...(data?.items ?? []).map((i) => i.time_ms)), [data]);

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <div className="space-y-4"><Skeleton className="h-8 w-60" /><Skeleton className="h-28 w-full" /><Skeleton className="h-64 w-full" /></div>;

  const items = data.items.filter((i) => filter === "all" || (filter === "flagged" ? i.flagged : i.status === filter));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs text-muted"><Link href="/tests" className="hover:text-text">Tests</Link> / Analysis</div>
          <h1 className="text-xl font-semibold tracking-tight">{data.test.title}</h1>
          <p className="mt-0.5 text-sm text-muted">Submitted {fmtDate(data.submitted_at)}{data.auto_submitted && " · auto-submitted when time ran out"}</p>
        </div>
        <Link href="/skills"><Button variant="secondary">See skill graph changes</Button></Link>
      </div>

      <Card>
        <div className="grid grid-cols-2 divide-border sm:grid-cols-3 lg:grid-cols-6 lg:divide-x">
          <Stat label="Score" value={<>{data.score}<span className="text-base text-muted"> / {data.max_score}</span></>} hint={data.test.negative_marking ? "incl. negative marks" : undefined} />
          <Stat label="Accuracy" value={pct(data.accuracy)} hint="of scored answers" />
          <Stat label="Correct" value={data.counts.correct} />
          <Stat label="Incorrect" value={data.counts.incorrect} />
          <Stat label="Unanswered" value={data.counts.unanswered} />
          <Stat label="Total time" value={fmtDuration(data.total_time_ms)} />
        </div>
        {data.counts.pending > 0 && (
          <div className="border-t border-border px-4 py-2 text-xs text-info">
            {data.counts.pending} coding/SQL answer(s) are saved but not scored yet — they will be judged by the Judge0 sandbox once Phase 3 is wired, and are excluded from the maximum score.
          </div>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <BreakdownTable title="By section" rows={data.sections} />
        <BreakdownTable title="By topic" rows={data.topics} />
      </div>

      <Card>
        <CardHeader title="Time per question" description="Measured while each question was on screen." />
        <div className="space-y-1.5 p-4">
          {data.items.map((it, i) => (
            <div key={it.tq_id} className="flex items-center gap-3 text-xs">
              <span className="tabular w-8 text-muted">Q{i + 1}</span>
              <div className="h-3 flex-1 overflow-hidden rounded-sm bg-surface-2">
                <div className="h-full rounded-sm" style={{
                  width: `${(it.time_ms / maxTime) * 100}%`,
                  background: it.status === "correct" ? "var(--ok)" : it.status === "incorrect" ? "var(--danger)" : "var(--muted)",
                }} />
              </div>
              <span className="tabular w-16 text-right text-text-2">{fmtDuration(it.time_ms)}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Question review" actions={
          <div className="flex flex-wrap gap-1">
            {(["all", "correct", "incorrect", "unanswered", "pending", "flagged"] as const).map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={clsx("h-7 rounded-md px-2 text-xs capitalize", filter === f ? "bg-surface-3 font-medium" : "text-muted hover:bg-surface-2")}>{f}</button>
            ))}
          </div>
        } />
        <div className="divide-y divide-border">
          {items.map((it) => {
            const n = data.items.indexOf(it) + 1;
            const key = describeKey(it.question, it.answer);
            return (
              <div key={it.tq_id}>
                <button onClick={() => setOpen(open === it.tq_id ? null : it.tq_id)} aria-expanded={open === it.tq_id}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-surface-2/60">
                  <span className="tabular w-8 text-xs text-muted">Q{n}</span>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{it.title}</span>
                  {it.flagged && <span className="text-xs text-ochre" title="Flagged">★</span>}
                  <span className="hidden text-xs text-muted sm:inline">{TYPE_LABEL[it.type]}</span>
                  <DifficultyBadge level={it.difficulty} />
                  <Badge tone={STATUS[it.status].tone}>{STATUS[it.status].label}</Badge>
                  <span className={clsx("tabular w-12 text-right text-sm", it.awarded > 0 ? "text-ok" : it.awarded < 0 ? "text-danger" : "text-muted")}>
                    {it.awarded > 0 ? "+" : ""}{it.awarded}
                  </span>
                </button>
                {open === it.tq_id && (
                  <div className="space-y-4 border-t border-border bg-surface-2/30 px-4 py-4">
                    <QuestionView q={it.question} hideOptions />
                    <AnswerInput q={it.question} value={it.response} onChange={() => undefined} disabled reveal={it.status === "pending" ? null : it.answer} />
                    {key && it.status !== "correct" && <p className="text-sm"><span className="text-muted">Correct answer: </span>{key}</p>}
                    {it.explanation && <p className="text-sm text-text-2">{it.explanation}</p>}
                    {it.feedback && <p className="text-xs text-muted">{it.feedback}</p>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
