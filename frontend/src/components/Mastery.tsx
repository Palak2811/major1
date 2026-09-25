import clsx from "clsx";

export function masteryTone(m: number | null | undefined) {
  if (m == null) return "var(--surface-3)";
  if (m < 40) return "var(--danger)";
  if (m < 70) return "var(--ochre)";
  return "var(--accent)";
}

export function MasteryBar({ value, className, showValue = true }: { value: number | null | undefined; className?: string; showValue?: boolean }) {
  return (
    <div className={clsx("flex items-center gap-2", className)}>
      <div className="h-1.5 flex-1 overflow-hidden rounded-sm bg-surface-2" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value ?? undefined} aria-label="Mastery">
        {value != null && <div className="h-full rounded-sm" style={{ width: `${Math.max(2, value)}%`, background: masteryTone(value) }} />}
      </div>
      {showValue && <span className="tabular w-9 text-right text-xs text-text-2">{value == null ? "—" : Math.round(value)}</span>}
    </div>
  );
}
