import type { Question } from "@/lib/types";
import { TYPE_LABEL } from "@/lib/types";
import { Badge, CompanyTag, DifficultyBadge, TopicTag } from "./ui";

function Code({ children }: { children: string }) {
  return <pre className="overflow-x-auto rounded-md border border-border bg-surface-2 p-3 font-mono text-xs leading-relaxed">{children}</pre>;
}

export function QuestionView({ q, hideOptions, hideTags }: { q: Question; hideOptions?: boolean; hideTags?: boolean }) {
  const meta = q.meta as Record<string, unknown>;
  const samples = (meta.samples as { input: string; output: string }[] | undefined) ?? [];
  return (
    <div className="space-y-4">
      {!hideTags && (
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge>{TYPE_LABEL[q.type]}</Badge>
          <DifficultyBadge level={q.difficulty} />
          {q.topic && <TopicTag name={q.topic.name} />}
          {q.companies.map((c) => <CompanyTag key={c.id} name={c.name} />)}
        </div>
      )}
      <p className="whitespace-pre-wrap text-base leading-relaxed">{q.body}</p>

      {typeof meta.code === "string" && <Code>{meta.code}</Code>}
      {typeof meta.schema_sql === "string" && (<div><div className="mb-1 text-xs font-medium text-text-2">Schema</div><Code>{meta.schema_sql}</Code></div>)}

      {q.type === "coding" && (
        <div className="grid gap-3 sm:grid-cols-3">
          {(["constraints", "input_format", "output_format"] as const).map((k) => (
            <div key={k}>
              <div className="mb-1 text-xs font-medium capitalize text-text-2">{k.replace("_", " ")}</div>
              <p className="text-sm text-text-2">{String(meta[k] ?? "")}</p>
            </div>
          ))}
        </div>
      )}
      {samples.map((s, i) => (
        <div key={i} className="grid gap-2 sm:grid-cols-2">
          <div><div className="mb-1 text-xs font-medium text-text-2">Sample input {i + 1}</div><Code>{s.input}</Code></div>
          <div><div className="mb-1 text-xs font-medium text-text-2">Sample output {i + 1}</div><Code>{s.output}</Code></div>
        </div>
      ))}

      {!hideOptions && q.options.length > 0 && (
        <ul className="space-y-1.5">
          {q.options.map((o) => (
            <li key={o.id} className="flex items-start gap-3 rounded-md border border-border px-3 py-2 text-sm">
              <span className="grid size-5 shrink-0 place-items-center rounded-sm bg-surface-2 font-mono text-2xs uppercase text-text-2">{o.id}</span>
              {o.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
