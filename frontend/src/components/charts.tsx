"use client";

/**
 * Chart primitives on Recharts, styled from design tokens.
 * Marks use --chart-1 / --chart-2 (validated categorical pair, light + dark).
 * Thin marks, 4px rounded bar ends, recessive grid, hover tooltips on every chart.
 */

import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";

const AXIS = { stroke: "var(--border-strong)", tick: { fill: "var(--muted)", fontSize: 11 }, tickLine: false };
const GRID = { stroke: "var(--border)", strokeDasharray: "0", vertical: false };

export function ChartTooltip({ active, payload, label, format }: TooltipProps<number, string> & { format?: (v: number, key: string) => string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-surface px-2.5 py-2 text-xs shadow-lg">
      {label != null && <div className="mb-1 font-medium text-text">{label}</div>}
      {payload.map((p) => (
        <div key={String(p.dataKey)} className="flex items-center gap-2 text-text-2">
          <span className="size-2 rounded-sm" style={{ background: p.color }} />
          <span>{p.name}</span>
          <span className="tabular ml-auto pl-3 font-medium text-text">{format ? format(Number(p.value), String(p.dataKey)) : p.value}</span>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap gap-3 text-xs text-text-2">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: i.color }} />{i.label}</span>
      ))}
    </div>
  );
}

export function AccuracyLine({ data }: { data: { date: string; accuracy: number | null; answered: number }[] }) {
  const rows = data.map((d) => ({ ...d, pct: d.accuracy == null ? null : Math.round(d.accuracy * 100), day: d.date.slice(5) }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
        <CartesianGrid {...GRID} />
        <XAxis dataKey="day" {...AXIS} interval="preserveStartEnd" minTickGap={24} />
        <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} {...AXIS} unit="%" />
        <Tooltip cursor={{ stroke: "var(--border-strong)" }}
          content={<ChartTooltip format={(v) => `${v}%`} />} />
        <Line type="monotone" dataKey="pct" name="Accuracy" stroke="var(--chart-1)" strokeWidth={2} connectNulls
          dot={{ r: 3.5, fill: "var(--chart-1)", stroke: "var(--surface)", strokeWidth: 2 }} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function HBar({ data, valueKey, labelKey, max = 100, unit = "", height, color = "var(--chart-1)", name }: {
  data: Record<string, string | number>[]; valueKey: string; labelKey: string; max?: number; unit?: string; height?: number; color?: string; name: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={height ?? Math.max(120, data.length * 28 + 24)}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 8 }} barCategoryGap={6}>
        <CartesianGrid stroke="var(--border)" horizontal={false} />
        <XAxis type="number" domain={[0, max]} {...AXIS} unit={unit} />
        <YAxis type="category" dataKey={labelKey} width={140} {...AXIS} tick={{ fill: "var(--text-2)", fontSize: 11 }} />
        <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<ChartTooltip format={(v) => `${Math.round(v)}${unit}`} />} />
        <Bar dataKey={valueKey} name={name} fill={color} radius={[0, 4, 4, 0]} maxBarSize={16} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function GroupedBars({ data, labelKey, series, height = 220 }: {
  data: Record<string, string | number>[]; labelKey: string; series: { key: string; name: string; color: string }[]; height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }} barGap={2} barCategoryGap="28%">
        <CartesianGrid {...GRID} />
        <XAxis dataKey={labelKey} {...AXIS} />
        <YAxis allowDecimals={false} {...AXIS} />
        <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<ChartTooltip />} />
        {series.map((s) => <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} radius={[4, 4, 0, 0]} maxBarSize={28} />)}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TimeBars({ data }: { data: { label: string; seconds: number; expected: number; correct: boolean }[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }} barCategoryGap={2}>
        <CartesianGrid {...GRID} />
        <XAxis dataKey="label" {...AXIS} tick={false} />
        <YAxis {...AXIS} unit="s" />
        <Tooltip cursor={{ fill: "var(--surface-2)" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload as (typeof data)[number];
            return (
              <div className="rounded-md border border-border bg-surface px-2.5 py-2 text-xs shadow-lg">
                <div className="mb-1 font-medium">{d.label}</div>
                <div className="tabular text-text-2">{d.seconds}s taken · {d.expected}s expected</div>
                <div className={d.correct ? "text-ok" : "text-danger"}>{d.correct ? "✓ correct" : "✗ incorrect"}</div>
              </div>
            );
          }} />
        <Bar dataKey="seconds" name="Time" radius={[4, 4, 0, 0]} maxBarSize={18}>
          {data.map((d, i) => <Cell key={i} fill={d.correct ? "var(--chart-1)" : "var(--chart-2)"} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
