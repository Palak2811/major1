"use client";

import { useState } from "react";
import { Badge, Card, CardHeader, EmptyState, ErrorState, PageHeader, SkeletonRows, Table, Td, Th } from "@/components/ui";
import { fmtDate, pct } from "@/lib/format";
import { useApi } from "@/lib/useApi";

interface Stats {
  days: number;
  mock: boolean;
  by_type: { call_type: string; calls: number; failures: number; cache_hits: number; prompt_tokens: number; completion_tokens: number; cost_usd: number; failure_rate: number; avg_latency_ms: number | null; p95_latency_ms: number | null }[];
  recent: { id: number; call_type: string; model: string; latency_ms: number; tokens: number; success: boolean; error: string | null; created_at: string }[];
}

export default function AIStatsPage() {
  const [days, setDays] = useState(7);
  const { data, error, loading, reload } = useApi<Stats>(`/ai/stats?days=${days}`);
  const total = data?.by_type.reduce((a, r) => ({ calls: a.calls + r.calls, tokens: a.tokens + r.prompt_tokens + r.completion_tokens, cost: a.cost + r.cost_usd }), { calls: 0, tokens: 0, cost: 0 });

  return (
    <div className="space-y-5">
      <PageHeader title="AI usage & reliability" description="Every LLM and embedding call is traced: latency, tokens, estimated list-price cost and failures."
        actions={<div className="flex rounded-md border border-border p-0.5">{[1, 7, 30].map((d) => (
          <button key={d} onClick={() => setDays(d)} aria-pressed={days === d} className={`h-7 rounded px-2.5 text-xs ${days === d ? "bg-surface-3 font-medium" : "text-muted"}`}>{d}d</button>))}</div>} />
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {data?.mock && <Badge tone="info">Mock mode — no GEMINI_API_KEY configured</Badge>}
      {total && (
        <Card><div className="tabular grid grid-cols-3 divide-x divide-border text-center">
          <div className="p-3"><div className="text-2xs uppercase text-muted">Calls</div><div className="text-2xl font-semibold">{total.calls}</div></div>
          <div className="p-3"><div className="text-2xs uppercase text-muted">Tokens</div><div className="text-2xl font-semibold">{total.tokens.toLocaleString()}</div></div>
          <div className="p-3"><div className="text-2xs uppercase text-muted">Est. cost (list price)</div><div className="text-2xl font-semibold">${total.cost.toFixed(4)}</div></div>
        </div></Card>
      )}
      <Card>
        <CardHeader title="By call type" description="Model routing: explain/hint/follow-up/revision use the fast model; evaluate/interviewer/code review/generation/parsing use the strong model." />
        {loading && !data ? <SkeletonRows rows={5} cols={6} /> : !data?.by_type.length ? <EmptyState title="No AI calls yet" /> : (
          <Table>
            <thead><tr><Th>Call type</Th><Th className="text-right">Calls</Th><Th className="text-right">Cache hits</Th><Th className="text-right">Failure rate</Th><Th className="text-right">Avg latency</Th><Th className="text-right">p95</Th><Th className="text-right">Tokens</Th><Th className="text-right">Est. cost</Th></tr></thead>
            <tbody>{data.by_type.map((r) => (
              <tr key={r.call_type}>
                <Td className="font-medium">{r.call_type}</Td>
                <Td className="tabular text-right">{r.calls}</Td>
                <Td className="tabular text-right text-text-2">{r.cache_hits}</Td>
                <Td className="tabular text-right">{r.failures ? <span className="text-danger">{pct(r.failure_rate, 1)}</span> : "0%"}</Td>
                <Td className="tabular text-right">{r.avg_latency_ms != null ? `${r.avg_latency_ms} ms` : "—"}</Td>
                <Td className="tabular text-right text-text-2">{r.p95_latency_ms != null ? `${r.p95_latency_ms} ms` : "—"}</Td>
                <Td className="tabular text-right">{(r.prompt_tokens + r.completion_tokens).toLocaleString()}</Td>
                <Td className="tabular text-right">${r.cost_usd.toFixed(4)}</Td>
              </tr>))}</tbody>
          </Table>
        )}
      </Card>
      <Card>
        <CardHeader title="Recent calls" />
        {!data?.recent.length ? <EmptyState title="No calls" /> : (
          <Table>
            <thead><tr><Th>When</Th><Th>Type</Th><Th>Model</Th><Th className="text-right">Latency</Th><Th className="text-right">Tokens</Th><Th>Status</Th></tr></thead>
            <tbody>{data.recent.map((r) => (
              <tr key={r.id}>
                <Td className="text-xs text-muted">{fmtDate(r.created_at)}</Td>
                <Td>{r.call_type}</Td>
                <Td className="text-xs text-text-2">{r.model}</Td>
                <Td className="tabular text-right">{r.latency_ms} ms</Td>
                <Td className="tabular text-right">{r.tokens}</Td>
                <Td>{r.success ? <Badge tone="ok">ok</Badge> : <Badge tone="danger" title={r.error ?? ""}>failed</Badge>}</Td>
              </tr>))}</tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
