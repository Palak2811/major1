"use client";

import { useState } from "react";
import type { AIEnvelope, Citation } from "@/lib/types";
import { Badge } from "./ui";

/** Every AI answer shows whether it is grounded, and its sources. Never hidden. */
export function GroundingBar({ env }: { env: Pick<AIEnvelope, "grounded" | "mock" | "cached" | "model" | "checks"> }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-2xs">
      {env.grounded ? <Badge tone="ok">✓ Grounded in course sources</Badge>
        : <Badge tone="warn">⚠ Not grounded — verify before relying on it</Badge>}
      {env.mock && <Badge tone="info">Mock AI (no API key)</Badge>}
      {env.cached && <Badge>Cached</Badge>}
      {env.checks?.input_flags?.length > 0 && <Badge tone="warn" title={env.checks.input_flags.join("; ")}>Input flagged</Badge>}
      {env.checks?.citations_dropped?.length > 0 && <Badge tone="neutral" title={`Dropped: ${env.checks.citations_dropped.join(", ")}`}>{env.checks.citations_dropped.length} invalid citation(s) removed</Badge>}
      {env.model && <span className="text-muted">{env.model}</span>}
    </div>
  );
}

export function Citations({ items }: { items: Citation[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!items.length) return null;
  return (
    <div className="space-y-1.5">
      <div className="text-2xs font-semibold uppercase tracking-wide text-muted">Sources</div>
      <ol className="space-y-1">
        {items.map((c, i) => (
          <li key={c.id} className="rounded-md border border-border text-xs">
            <button className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left hover:bg-surface-2" onClick={() => setOpen(open === c.id ? null : c.id)} aria-expanded={open === c.id}>
              <span className="tabular grid size-4 shrink-0 place-items-center rounded-sm bg-info-soft text-2xs text-info">{i + 1}</span>
              <span className="flex-1 truncate font-medium">{c.title}</span>
              {c.topic && <span className="text-muted">{c.topic}</span>}
              <span className="tabular text-muted" title="Retrieval similarity">{c.score.toFixed(2)}</span>
            </button>
            {open === c.id && <p className="border-t border-border px-2.5 py-2 leading-relaxed text-text-2">{c.snippet}…</p>}
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Replace inline [S12] markers with numbered superscripts that match the source list. */
export function CitedText({ text, citations }: { text: string; citations: Citation[] }) {
  const index = new Map(citations.map((c, i) => [c.ref, i + 1]));
  const parts = text.split(/(\[S\d+\])/g);
  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      {parts.map((p, i) => {
        const m = /^\[(S\d+)\]$/.exec(p);
        if (!m) return <span key={i}>{p}</span>;
        const n = index.get(m[1]);
        return n ? <sup key={i} className="ml-0.5 text-2xs font-semibold text-info">[{n}]</sup> : null;
      })}
    </p>
  );
}
