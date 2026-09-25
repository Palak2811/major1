"use client";

import clsx from "clsx";
import { useMemo, useState } from "react";
import { MasteryBar } from "@/components/Mastery";
import { Card, DifficultyBadge, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { fmtDuration, pct } from "@/lib/format";
import type { SkillNode } from "@/lib/types";
import { useApi } from "@/lib/useApi";

function ago(iso: string | null) {
  if (!iso) return "—";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  return days <= 0 ? "today" : days === 1 ? "yesterday" : `${days} days ago`;
}

export default function SkillGraphPage() {
  const { data, error, loading, reload } = useApi<SkillNode[]>("/me/skills");
  const [open, setOpen] = useState<Record<number, boolean>>({});

  const { roots, kids } = useMemo(() => {
    const kids = new Map<number | null, SkillNode[]>();
    (data ?? []).forEach((n) => kids.set(n.parent_id, [...(kids.get(n.parent_id) ?? []), n]));
    const order = ["DSA", "DBMS", "OS", "CN", "OOP", "Aptitude"];
    const roots = (kids.get(null) ?? []).sort((a, b) => order.indexOf(a.area) - order.indexOf(b.area));
    return { roots, kids };
  }, [data]);

  function Node({ n, depth }: { n: SkillNode; depth: number }) {
    const children = kids.get(n.id) ?? [];
    const isOpen = open[n.id] ?? depth < 1;
    const value = depth === 0 || children.length ? n.rollup : n.mastery_score;
    return (
      <>
        <div className={clsx("grid grid-cols-[1fr_auto] items-center gap-3 px-4 py-2 md:grid-cols-[minmax(0,1.4fr)_minmax(120px,1fr)_60px_70px_70px_80px_90px]",
          depth === 0 && "bg-surface-2/60")}>
          <button className="flex min-w-0 items-center gap-1.5 text-left text-sm" style={{ paddingLeft: depth * 18 }}
            onClick={() => children.length && setOpen({ ...open, [n.id]: !isOpen })} aria-expanded={children.length ? isOpen : undefined}>
            <span className="w-3 text-muted">{children.length ? (isOpen ? "▾" : "▸") : ""}</span>
            <span className={clsx("truncate", depth === 0 ? "font-semibold" : depth === 1 ? "font-medium" : "text-text-2")}>{n.name}</span>
          </button>
          <MasteryBar value={value} />
          <span className="tabular hidden text-right text-xs text-text-2 md:block">{depth === 0 || children.length ? n.rollup_attempts : n.attempt_count}</span>
          <span className="tabular hidden text-right text-xs text-text-2 md:block">{pct(n.accuracy)}</span>
          <span className="tabular hidden text-right text-xs text-text-2 md:block" title="Self-reported confidence (0–100%)">{pct(n.confidence)}</span>
          <span className="tabular hidden text-right text-xs text-text-2 md:block">{n.average_time_ms ? fmtDuration(n.average_time_ms) : "—"}</span>
          <span className="hidden text-right text-xs text-muted md:block">{ago(n.last_attempt)}</span>
        </div>
        {isOpen && children.map((c) => <Node key={c.id} n={c} depth={depth + 1} />)}
      </>
    );
  }

  return (
    <div>
      <PageHeader title="Skill graph"
        description="Mastery per node, updated after every study cycle and test. Parent nodes roll up their subtree, weighted by attempts." />
      {error && <ErrorState message={error.message} onRetry={reload} />}
      <Card>
        <div className="hidden grid-cols-[minmax(0,1.4fr)_minmax(120px,1fr)_60px_70px_70px_80px_90px] gap-3 border-b border-border px-4 py-2 text-2xs font-semibold uppercase tracking-wide text-muted md:grid">
          <span>Skill</span><span>Mastery</span><span className="text-right">Attempts</span><span className="text-right">Accuracy</span>
          <span className="text-right">Confidence</span><span className="text-right">Avg time</span><span className="text-right">Last practised</span>
        </div>
        {loading && !data ? <SkeletonRows rows={10} cols={5} /> : roots.length === 0 ? <EmptyState title="No skills yet" /> : (
          <div className="divide-y divide-border">{roots.map((r) => <Node key={r.id} n={r} depth={0} />)}</div>
        )}
      </Card>
      <p className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
        Next practice difficulty is picked from mastery: <DifficultyBadge level="easy" /> below 35 · <DifficultyBadge level="medium" /> 35–70 · <DifficultyBadge level="hard" /> above 70.
      </p>
    </div>
  );
}
