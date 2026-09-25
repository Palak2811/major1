"use client";

import clsx from "clsx";
import { useState } from "react";
import { QuestionView } from "@/components/QuestionView";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, Field, PageHeader, Select, SkeletonRows } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { ReviewQuestion, Topic } from "@/lib/types";
import { TYPE_LABEL } from "@/lib/types";
import { useApi } from "@/lib/useApi";

const CHECK_LABEL: Record<string, string> = {
  schema: "Schema (JSON contract)", contract: "Question contract", citations: "Citations valid",
  safety: "Safety filter", consistency: "Internal consistency",
};

function CheckRow({ name, value }: { name: string; value: string }) {
  const tone = value === "pass" ? "ok" : value.startsWith("pending") ? "info" : "danger";
  return (
    <div className="flex items-start gap-2 text-xs">
      <Badge tone={tone}>{value === "pass" ? "✓ pass" : value.startsWith("pending") ? "… pending" : "✗ fail"}</Badge>
      <span className="font-medium">{CHECK_LABEL[name] ?? name}</span>
      {value !== "pass" && <span className="text-muted">{value.replace(/^(fail|pending): ?/, "")}</span>}
    </div>
  );
}

export default function ReviewQueuePage() {
  const [state, setState] = useState<"pending" | "rejected" | "all">("pending");
  const queue = useApi<ReviewQuestion[]>(`/ai/review-queue?state=${state}`);
  const topics = useApi<Topic[]>("/topics");
  const [gen, setGen] = useState({ topic_id: "", type: "mcq", difficulty: "medium" });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy("gen"); setError(null);
    try {
      await api("/ai/questions/generate", { method: "POST", json: { ...gen, topic_id: Number(gen.topic_id) } });
      setState("pending");
      await queue.reload();
    } catch (err) { setError(err instanceof ApiError ? err.message : "Generation failed"); }
    finally { setBusy(null); }
  }

  async function decide(q: ReviewQuestion, action: "approve" | "reject" | "revalidate") {
    setBusy(`${action}-${q.id}`); setError(null);
    try { await api(`/ai/review-queue/${q.id}/${action}`, { method: "POST", json: {} }); await queue.reload(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Action failed"); }
    finally { setBusy(null); }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="AI review queue"
        description="AI-generated questions stay invisible to students until a content manager approves them. Approval is blocked unless every automated check passed." />
      {error && <ErrorState message={error} />}

      <Card>
        <CardHeader title="Generate a draft" description="Grounded in the knowledge base for the chosen topic. Coding drafts are validated by running their reference solution on Judge0." />
        <form onSubmit={generate} className="flex flex-wrap items-end gap-3 p-4">
          <div className="w-64"><Field label="Topic">
            <Select required value={gen.topic_id} onChange={(e) => setGen({ ...gen, topic_id: e.target.value })}>
              <option value="">Choose…</option>
              {(topics.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.area} · {t.name}</option>)}
            </Select></Field></div>
          <div className="w-36"><Field label="Type">
            <Select value={gen.type} onChange={(e) => setGen({ ...gen, type: e.target.value })}><option value="mcq">MCQ</option><option value="coding">Coding</option></Select></Field></div>
          <div className="w-36"><Field label="Difficulty">
            <Select value={gen.difficulty} onChange={(e) => setGen({ ...gen, difficulty: e.target.value })}><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></Select></Field></div>
          <Button type="submit" loading={busy === "gen"}>Generate</Button>
        </form>
      </Card>

      <div className="flex gap-1" role="tablist">
        {(["pending", "rejected", "all"] as const).map((s) => (
          <button key={s} role="tab" aria-selected={state === s} onClick={() => setState(s)}
            className={clsx("h-8 rounded-md px-3 text-sm capitalize", state === s ? "bg-surface-3 font-medium" : "text-muted hover:bg-surface-2")}>{s}</button>
        ))}
        <Button variant="ghost" size="sm" className="ml-auto" onClick={queue.reload}>Refresh</Button>
      </div>

      {queue.error ? <ErrorState message={queue.error.message} onRetry={queue.reload} /> :
        queue.loading && !queue.data ? <Card><SkeletonRows rows={3} cols={3} /></Card> :
          !queue.data?.length ? <Card><EmptyState title="Nothing here" description={state === "pending" ? "Generated drafts awaiting review appear here." : undefined} /></Card> : (
            <div className="space-y-4">
              {queue.data.map((q) => {
                const r = q.review;
                const ready = r.status === "ready_for_review";
                const coding = q.type === "coding";
                return (
                  <Card key={q.id}>
                    <CardHeader
                      title={<span className="flex items-center gap-2">{q.title} <Badge>{TYPE_LABEL[q.type]}</Badge>
                        <Badge tone={q.status === "published" ? "ok" : q.status === "rejected" ? "danger" : ready ? "accent" : "info"}>{q.status === "review" ? r.status.replaceAll("_", " ") : q.status}</Badge>
                        {r.mock && <Badge tone="info">Mock AI</Badge>}</span>}
                      description={`${q.topic?.name ?? "—"} · ${q.difficulty} · generated by ${r.generated_by} · ${fmtDate(q.created_at)}`}
                      actions={q.status === "review" ? (
                        <>
                          {coding && r.checks.consistency?.startsWith("pending") && <Button size="sm" variant="ghost" loading={busy === `revalidate-${q.id}`} onClick={() => decide(q, "revalidate")}>Re-run judge</Button>}
                          <Button size="sm" variant="secondary" loading={busy === `reject-${q.id}`} onClick={() => decide(q, "reject")}>Reject</Button>
                          <Button size="sm" disabled={!ready} title={ready ? undefined : "All checks must pass first"} loading={busy === `approve-${q.id}`} onClick={() => decide(q, "approve")}>Approve & publish</Button>
                        </>
                      ) : undefined} />
                    <div className="grid gap-5 p-4 lg:grid-cols-[1fr_280px]">
                      <div className="space-y-3">
                        <QuestionView q={q} hideTags />
                        {q.type === "mcq" && <p className="text-sm"><span className="text-muted">Answer: </span>{q.options.find((o) => (q.answer?.correct as string[])?.includes(o.id))?.text}</p>}
                        {coding && (
                          <details className="text-sm"><summary className="cursor-pointer text-accent">Hidden tests & reference solution (never shown to students)</summary>
                            <pre className="mt-2 max-h-60 overflow-auto rounded-md bg-surface-2 p-2 font-mono text-xs">{JSON.stringify(q.answer, null, 2)}</pre></details>
                        )}
                        {q.explanation && <p className="text-sm text-text-2">{q.explanation}</p>}
                      </div>
                      <div className="space-y-2">
                        <div className="text-2xs font-semibold uppercase tracking-wide text-muted">Automated checks</div>
                        {Object.entries(r.checks).map(([k, v]) => <CheckRow key={k} name={k} value={v} />)}
                        <div className="pt-2 text-2xs font-semibold uppercase tracking-wide text-muted">Grounded in</div>
                        {r.citations.length ? r.citations.map((c) => <div key={c.id} className="text-xs">{c.title}</div>) : <div className="text-xs text-danger">No valid citations</div>}
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
    </div>
  );
}
