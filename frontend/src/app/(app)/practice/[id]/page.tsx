"use client";

import clsx from "clsx";
import Link from "next/link";
import { use, useState } from "react";
import { CodeWorkbench } from "@/components/CodeWorkbench";
import { QuestionView } from "@/components/QuestionView";
import { Badge, ErrorState, Skeleton } from "@/components/ui";
import { fmtDate } from "@/lib/format";
import { LANG_LABEL, type SubmissionView, VERDICT_TONE } from "@/lib/judge";
import type { Question } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export default function ProblemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const q = useApi<Question>(`/questions/${id}`);
  const history = useApi<SubmissionView[]>(`/submissions?question_id=${id}&mode=submit`);
  const [tab, setTab] = useState<"problem" | "submissions">("problem");

  if (q.error) return <ErrorState message={q.error.status === 404 ? "Problem not found" : q.error.message} onRetry={q.reload} />;
  if (!q.data) return <div className="grid gap-4 lg:grid-cols-2"><Skeleton className="h-96" /><Skeleton className="h-96" /></div>;
  const question = q.data;
  if (question.type !== "coding" && question.type !== "sql") {
    return <ErrorState message="This question isn't a coding problem." />;
  }

  return (
    <div className="flex flex-col gap-3 lg:h-[calc(100vh-7.5rem)]">
      <div className="text-xs text-muted"><Link href="/practice" className="hover:text-text">Coding practice</Link> / {question.title}</div>
      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-surface">
          <div className="flex gap-1 border-b border-border px-2 pt-2" role="tablist">
            {(["problem", "submissions"] as const).map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                className={clsx("rounded-t-md px-3 py-1.5 text-sm capitalize", tab === t ? "bg-surface-2 font-medium" : "text-muted hover:text-text")}>
                {t}{t === "submissions" && history.data?.length ? ` (${history.data.length})` : ""}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {tab === "problem" ? (
              <>
                <h1 className="mb-3 text-xl font-semibold tracking-tight">{question.title}</h1>
                <QuestionView q={question} />
                {question.type === "coding" && (
                  <p className="mt-5 text-xs text-muted">
                    Limits: {Number(question.meta.time_limit_ms ?? 2000) / 1000}s CPU · {String(question.meta.memory_limit_mb ?? 256)} MB. Read from stdin, write to stdout.
                    Java code must use a public class named <code className="font-mono">Main</code>.
                  </p>
                )}
              </>
            ) : history.loading ? <Skeleton className="h-24 w-full" /> : !history.data?.length ? (
              <p className="text-sm text-muted">No submissions yet.</p>
            ) : (
              <ul className="divide-y divide-border">
                {history.data.map((s) => (
                  <li key={s.id} className="flex items-center gap-3 py-2 text-sm">
                    <Badge tone={VERDICT_TONE[s.verdict?.status ?? ""] ?? "neutral"}>{s.verdict?.label}</Badge>
                    <span className="text-xs text-text-2">{LANG_LABEL[s.language]}</span>
                    {s.verdict?.details.total ? <span className="tabular text-xs text-muted">{s.verdict.details.passed}/{s.verdict.details.total}</span> : null}
                    <span className="ml-auto text-xs text-muted">{fmtDate(s.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <div className="min-h-[560px] lg:min-h-0">
          <CodeWorkbench questionId={question.id} isSql={question.type === "sql"} onSubmitted={() => history.reload()} />
        </div>
      </div>
    </div>
  );
}
