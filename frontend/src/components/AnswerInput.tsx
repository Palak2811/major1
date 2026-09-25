"use client";

import clsx from "clsx";
import type { Answer, Question } from "@/lib/types";
import { CodeWorkbench } from "./CodeWorkbench";
import { Badge, Input, Textarea } from "./ui";

/** Type-aware answer control used by Study Mode and Test Mode. */
export function AnswerInput({ q, value, onChange, disabled, reveal }: {
  q: Question;
  value: Answer | null;
  onChange: (a: Answer) => void;
  disabled?: boolean;
  /** After grading: the key, to colour options. */
  reveal?: Record<string, unknown> | null;
}) {
  const selected = value?.selected ?? [];
  const correct = (reveal?.correct as string[] | undefined) ?? null;

  if (q.type === "mcq" || q.type === "multi_select") {
    const multi = q.type === "multi_select";
    return (
      <div className="space-y-1.5" role={multi ? "group" : "radiogroup"}>
        {multi && <p className="text-xs text-muted">Select all that apply.</p>}
        {q.options.map((o) => {
          const on = selected.includes(o.id);
          const isKey = correct?.includes(o.id);
          return (
            <label key={o.id}
              className={clsx(
                "flex cursor-pointer items-start gap-3 rounded-md border px-3 py-2.5 text-sm transition-colors",
                disabled && "cursor-default",
                correct ? (isKey ? "border-ok bg-ok-soft" : on ? "border-danger bg-danger-soft" : "border-border")
                  : on ? "border-accent bg-accent-soft" : "border-border hover:bg-surface-2",
              )}>
              <input type={multi ? "checkbox" : "radio"} name={`q-${q.id}`} className="mt-0.5 accent-[var(--accent)]"
                checked={on} disabled={disabled}
                onChange={() => onChange({ selected: multi ? (on ? selected.filter((x) => x !== o.id) : [...selected, o.id]) : [o.id] })} />
              <span className="flex-1">{o.text}</span>
              {correct && isKey && <Badge tone="ok">Correct</Badge>}
            </label>
          );
        })}
      </div>
    );
  }

  if (q.type === "numerical") {
    return (
      <div className="max-w-xs">
        <Input type="number" step="any" inputMode="decimal" aria-label="Your answer" placeholder="Enter a number"
          disabled={disabled} value={value?.value ?? ""}
          onChange={(e) => onChange(e.target.value === "" ? {} : { value: Number(e.target.value) })} />
      </div>
    );
  }

  if (q.type === "coding" || q.type === "sql") {
    return (
      <div className="h-[460px]">
        <CodeWorkbench questionId={q.id} isSql={q.type === "sql"} mode="test" disabled={disabled}
          value={value} onChange={(v) => onChange({ code: v.code, language: v.language })} />
      </div>
    );
  }

  const placeholder = {
    output_prediction: "Exact output, as printed",
    debugging: "Describe the bug and paste the corrected line(s)",
    theory: "Write your answer",
  }[q.type] ?? "";
  return (
    <Textarea rows={q.type === "theory" ? 6 : q.type === "output_prediction" ? 3 : 5} aria-label="Your answer"
      className={clsx(q.type !== "theory" && "font-mono text-xs")} placeholder={placeholder} disabled={disabled}
      value={value?.text ?? ""} onChange={(e) => onChange({ text: e.target.value })} />
  );
}

export function describeKey(q: Question, key: Record<string, unknown>): string | null {
  switch (q.type) {
    case "mcq":
    case "multi_select": {
      const ids = (key.correct as string[]) ?? [];
      return q.options.filter((o) => ids.includes(o.id)).map((o) => o.text).join("; ");
    }
    case "numerical":
      return `${key.value}${key.tolerance ? ` (± ${key.tolerance})` : ""}`;
    case "output_prediction":
      return String(key.expected_output ?? "");
    case "debugging":
      return String(key.fix ?? "");
    case "theory":
      return ((key.key_points as string[]) ?? []).join(" · ");
    case "sql":
      return String(key.reference_query ?? "");
    default:
      return null;
  }
}
