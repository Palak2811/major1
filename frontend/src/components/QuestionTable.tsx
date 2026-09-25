"use client";

import Link from "next/link";
import { useState } from "react";
import type { Page, Question } from "@/lib/types";
import { TYPE_LABEL } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { Badge, Button, CompanyTag, DifficultyBadge, EmptyState, ErrorState, SkeletonRows, Table, Td, Th, TopicTag } from "./ui";

export function QuestionTable({ filter = "", hrefBase = "/questions", admin, onEdit, emptyText = "Try clearing some filters." }: {
  filter?: string; hrefBase?: string; admin?: boolean; onEdit?: (q: Question) => void; emptyText?: string;
}) {
  const [page, setPage] = useState(1);
  const qs = `page=${page}&page_size=20${filter ? `&${filter}` : ""}`;
  const { data, error, loading, reload } = useApi<Page<Question>>(`/questions?${qs}`);

  if (error) return <div className="p-4"><ErrorState message={error.message} onRetry={reload} /></div>;
  if (loading && !data) return <SkeletonRows rows={6} cols={4} />;
  if (!data || data.items.length === 0) return <EmptyState title="No questions here" description={emptyText} />;

  const pages = Math.ceil(data.total / data.page_size);
  return (
    <div>
      <Table>
        <thead><tr><Th>Title</Th><Th>Type</Th><Th>Difficulty</Th><Th>Topic</Th><Th>Companies</Th>{admin && <Th>Status</Th>}{admin && <Th />}</tr></thead>
        <tbody>
          {data.items.map((q) => (
            <tr key={q.id} className="hover:bg-surface-2/60">
              <Td className="max-w-xs">
                {admin ? <span className="font-medium">{q.title}</span> : <Link href={`${hrefBase}/${q.id}`} className="font-medium hover:text-accent">{q.title}</Link>}
              </Td>
              <Td><span className="text-xs text-text-2">{TYPE_LABEL[q.type]}</span></Td>
              <Td><DifficultyBadge level={q.difficulty} /></Td>
              <Td>{q.topic ? <TopicTag name={q.topic.name} /> : <span className="text-xs text-muted">—</span>}</Td>
              <Td><div className="flex flex-wrap gap-1">{q.companies.map((c) => <CompanyTag key={c.id} name={c.name} />)}</div></Td>
              {admin && <Td><Badge tone={q.status === "published" ? "ok" : q.status === "draft" ? "neutral" : "danger"}>{q.status}</Badge></Td>}
              {admin && <Td className="text-right"><Button size="sm" variant="ghost" onClick={() => onEdit?.(q)}>Edit</Button></Td>}
            </tr>
          ))}
        </tbody>
      </Table>
      <div className="flex items-center justify-between px-3 py-2 text-xs text-muted">
        <span className="tabular">{data.total} total</span>
        {pages > 1 && (
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <span className="tabular">{page} / {pages}</span>
            <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        )}
      </div>
    </div>
  );
}
