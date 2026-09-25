"use client";

import Link from "next/link";
import { use } from "react";
import { QuestionView } from "@/components/QuestionView";
import { Card, ErrorState, Skeleton } from "@/components/ui";
import type { Question } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export default function QuestionDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: q, error, reload } = useApi<Question>(`/questions/${id}`);

  if (error) return <ErrorState message={error.status === 404 ? "Question not found" : error.message} onRetry={reload} />;
  return (
    <div className="space-y-4">
      <div className="text-xs text-muted"><Link href="/questions" className="hover:text-text">Question bank</Link> / {q?.title ?? "…"}</div>
      <Card className="p-5">
        {!q ? <div className="space-y-3"><Skeleton className="h-6 w-2/3" /><Skeleton className="h-24 w-full" /></div> : (
          <>
            <h1 className="mb-4 text-xl font-semibold tracking-tight">{q.title}</h1>
            <QuestionView q={q} />
          </>
        )}
      </Card>
      {q && (q.type === "coding" || q.type === "sql") ? (
        <Link href={`/practice/${q.id}`} className="inline-block text-sm font-medium text-accent hover:underline">Solve this in the code editor →</Link>
      ) : (
        <p className="text-xs text-muted">Practise this topic in <Link href="/study" className="text-accent hover:underline">Study mode</Link> or a timed test.</p>
      )}
    </div>
  );
}
