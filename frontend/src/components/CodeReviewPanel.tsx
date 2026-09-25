"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { SubmissionView } from "@/lib/judge";
import type { CodeReview } from "@/lib/types";
import { Badge, Button, Skeleton } from "./ui";

function Items({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="mb-1 text-2xs font-semibold uppercase tracking-wide text-muted">{title}</div>
      <ul className="list-disc space-y-0.5 pl-4 text-sm text-text-2">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  );
}

/** AI review of a *judged* submission. It annotates Judge0's verdict and can never change it. */
export function CodeReviewPanel({ sub }: { sub: SubmissionView }) {
  const [review, setReview] = useState<CodeReview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const v = sub.verdict;
  if (!v?.done || sub.mode === "run" || v.status === "internal_error") return null;

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ review: CodeReview }>(`/submissions/${sub.id}/review`, { method: "POST" });
      setReview(r.review);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Review unavailable");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-t border-border p-4">
      {!review && !busy && (
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-muted">Get AI feedback on complexity, style and edge cases. The verdict above is final — the review only explains it.</p>
          <Button size="sm" variant="secondary" onClick={load}>AI code review</Button>
        </div>
      )}
      {busy && <div className="space-y-2"><Skeleton className="h-4 w-40" /><Skeleton className="h-16 w-full" /></div>}
      {error && <p className="text-sm text-danger">{error}</p>}
      {review && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">AI code review</span>
            <Badge>Time {review.time_complexity}</Badge>
            <Badge>Space {review.space_complexity}</Badge>
            {review.mock && <Badge tone="info">Mock AI</Badge>}
            <span className="ml-auto text-2xs text-muted">Annotates the Judge0 verdict “{v.label}” · {review.model}</span>
          </div>
          {review.summary && <p className="text-sm leading-relaxed">{review.summary}</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Items title="Code quality" items={review.quality} />
            <Items title="Edge cases" items={review.edge_cases} />
            <Items title="Potential defects" items={review.potential_defects} />
            {review.alternative_approach && <Items title="Alternative approach" items={[review.alternative_approach]} />}
          </div>
          {review.removed_contradictions.length > 0 && (
            <p className="text-2xs text-muted">{review.removed_contradictions.length} statement(s) that contradicted the judge&rsquo;s verdict were removed.</p>
          )}
        </div>
      )}
    </div>
  );
}
