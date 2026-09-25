import Link from "next/link";
import type { Company, SkillWeights } from "@/lib/types";
import { Badge, Card, DifficultyBadge } from "./ui";

/** Mandatory label wherever company pattern data appears (text comes from the API). */
export function PatternDisclaimer({ text, compact }: { text: string; compact?: boolean }) {
  return (
    <div role="note" className="flex gap-2 rounded-md border border-warn/30 bg-warn-soft px-3 py-2 text-xs text-warn">
      <svg viewBox="0 0 16 16" className="mt-0.5 size-3.5 shrink-0" aria-hidden><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M8 4.5v4M8 10.8v.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
      <span>{compact ? "Observed historical preparation pattern, not an official specification." : text}</span>
    </div>
  );
}

const WEIGHT_LABEL: Record<keyof SkillWeights, string> = {
  dsa: "DSA", oop: "OOP", dbms: "DBMS", os: "OS", aptitude: "Aptitude", hr: "HR",
};
const WEIGHT_COLOR: Record<keyof SkillWeights, string> = {
  dsa: "var(--accent)", oop: "var(--info)", dbms: "var(--ochre)", os: "#7a6aa8", aptitude: "#b85c7c", hr: "var(--muted)",
};

export function SkillWeightBar({ weights }: { weights: SkillWeights }) {
  const entries = (Object.keys(WEIGHT_LABEL) as (keyof SkillWeights)[]).filter((k) => weights[k] > 0);
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-sm bg-surface-2">
        {entries.map((k) => (
          <div key={k} style={{ width: `${weights[k]}%`, background: WEIGHT_COLOR[k] }} title={`${WEIGHT_LABEL[k]} ${weights[k]}%`} />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
        {entries.map((k) => (
          <span key={k} className="inline-flex items-center gap-1.5 text-xs text-text-2">
            <span className="size-2 rounded-sm" style={{ background: WEIGHT_COLOR[k] }} />
            {WEIGHT_LABEL[k]} <span className="tabular text-muted">{weights[k]}%</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export function CompanyCard({ c }: { c: Company }) {
  return (
    <Link href={`/companies/${c.slug}`} className="block">
      <Card className="h-full p-4 transition-colors hover:border-border-strong">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="font-semibold">{c.name}</h3>
            <p className="mt-0.5 line-clamp-2 text-xs text-muted">{c.description || "No description."}</p>
          </div>
          <DifficultyBadge level={c.oa_pattern.difficulty} />
        </div>
        <dl className="tabular mt-4 grid grid-cols-3 gap-2 text-center">
          {[["Coding", c.oa_pattern.coding_questions], ["MCQs", c.oa_pattern.mcqs], ["Minutes", c.oa_pattern.duration_minutes]].map(([l, v]) => (
            <div key={l} className="rounded-md bg-surface-2 py-1.5">
              <dd className="text-sm font-semibold">{v}</dd>
              <dt className="text-2xs text-muted">{l}</dt>
            </div>
          ))}
        </dl>
        <div className="mt-4"><SkillWeightBar weights={c.skill_weights} /></div>
        <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
          <Badge tone="warn" title={c.pattern_disclaimer}>Observed pattern · not official</Badge>
          <span className="text-xs text-muted">{c.question_count} tagged questions</span>
        </div>
      </Card>
    </Link>
  );
}
