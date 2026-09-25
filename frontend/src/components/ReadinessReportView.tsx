"use client";

import Link from "next/link";
import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { ChartTooltip } from "./charts";
import { PatternDisclaimer } from "./company";
import { MasteryBar } from "./Mastery";
import { Badge, Button, Card, CardHeader, Table, Td, Th } from "./ui";
import type { ReadinessReport } from "@/lib/types";

export function ReadinessReportView({ r }: { r: ReadinessReport }) {
  const rec = r.recommendation;
  const href = rec.action === "code" ? (rec.question_id ? `/practice/${rec.question_id}` : "/practice") : "/study";
  const weakest = [...r.components].filter((c) => c.available).sort((a, b) => a.value - b.value)[0];

  return (
    <div className="space-y-5">
      {r.company && <PatternDisclaimer text={r.company.pattern_disclaimer} />}

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-5">
          <div className="text-2xs font-semibold uppercase tracking-wide text-muted">Overall readiness</div>
          <div className="tabular mt-1 text-5xl font-semibold tracking-tight">{r.overall.toFixed(1)}<span className="text-2xl text-muted">%</span></div>
          <p className="mt-2 text-xs text-muted">
            {r.custom_weights ? `${r.company?.name} emphasises some areas more, so its own weights are used.` : r.formula}
          </p>
          {r.history.length > 1 && (
            <div className="mt-3 h-14" aria-label="Readiness history">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={r.history.map((h) => ({ ...h, t: new Date(h.at).toLocaleDateString() }))}>
                  <YAxis hide domain={[0, 100]} />
                  <Tooltip content={<ChartTooltip format={(v) => `${v}%`} />} labelFormatter={(_, p) => p?.[0]?.payload?.t} />
                  <Line dataKey="overall" name="Readiness" stroke="var(--chart-1)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Recommended next step" description="Rule-based: targets the component with the largest weighted gap." />
          <div className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <div className="text-lg font-semibold">{rec.title}</div>
              <p className="mt-0.5 text-sm text-text-2">{rec.detail}</p>
              {weakest && <p className="mt-1 text-xs text-muted">Lowest measured component: {weakest.label} ({Math.round(weakest.value)}).</p>}
            </div>
            <Link href={href}><Button>{rec.action === "code" ? "Open problem" : "Start studying"}</Button></Link>
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Per-domain breakdown" description="Each component is on a 0–100 scale; contribution = weight × value." />
        <Table>
          <thead><tr><Th>Component</Th><Th className="w-64">Value</Th><Th className="text-right">Weight</Th><Th className="text-right">Contribution</Th><Th>Evidence</Th></tr></thead>
          <tbody>
            {r.components.map((c) => (
              <tr key={c.key}>
                <Td className="font-medium">{c.label}{!c.available && <Badge className="ml-2" tone={c.key === "interview" ? "info" : "neutral"}>{c.key === "interview" ? "Phase 5" : "no data"}</Badge>}</Td>
                <Td><MasteryBar value={c.available ? c.value : null} /></Td>
                <Td className="tabular text-right text-text-2">{Math.round(c.weight * 100)}%</Td>
                <Td className="tabular text-right">{c.contribution.toFixed(1)}</Td>
                <Td className="text-xs text-muted">{c.detail}</Td>
              </tr>
            ))}
            <tr>
              <Td className="font-semibold">Total</Td><Td /><Td className="tabular text-right text-text-2">100%</Td>
              <Td className="tabular text-right font-semibold">{r.overall.toFixed(1)}</Td><Td />
            </tr>
          </tbody>
        </Table>
      </Card>

      <Card>
        <CardHeader title="Biggest weaknesses" description={r.company ? `Weighted by how much ${r.company.name} emphasises each area.` : "Weighted by the default readiness weights."} />
        {r.weaknesses.length === 0 ? (
          <p className="p-4 text-sm text-muted">No weaknesses identified yet — practise a few topics first.</p>
        ) : (
          <div className="divide-y divide-border">
            {r.weaknesses.map((w) => (
              <div key={w.name} className="flex items-center gap-4 px-4 py-2.5">
                <div className="w-48 min-w-0">
                  <div className="truncate text-sm font-medium">{w.name}</div>
                  <div className="text-2xs text-muted">{w.area} · {w.reason}</div>
                </div>
                <MasteryBar value={w.mastery} className="flex-1" />
                <span className="tabular w-20 text-right text-xs text-muted">priority {w.priority}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
