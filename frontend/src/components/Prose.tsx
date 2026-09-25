import type { TeachingBlock } from "@/lib/types";
import { Badge } from "./ui";

/** Minimal, safe renderer: paragraphs + **bold**. No HTML injection. */
export function Prose({ text }: { text: string }) {
  return (
    <div className="space-y-3 text-base leading-relaxed text-text">
      {text.split(/\n{2,}/).map((para, i) => (
        <p key={i} className="whitespace-pre-wrap">
          {para.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
            part.startsWith("**") && part.endsWith("**")
              ? <strong key={j} className="font-semibold">{part.slice(2, -2)}</strong>
              : <span key={j}>{part}</span>)}
        </p>
      ))}
    </div>
  );
}

export function TeachingCard({ block, fallback, note }: { block: TeachingBlock | null; fallback: string; note?: string }) {
  if (!block) {
    return <p className="text-sm text-muted">{fallback}</p>;
  }
  const ai = block.provider.startsWith("rag");
  // Map inline [S12] source ids to the numbered source list below.
  const order = new Map(block.sources.map((s, i) => [`S${s.document_id}`, i + 1]));
  const body = block.body.replace(/\[(S\d+)\]/g, (_, ref: string) => (order.has(ref) ? `[${order.get(ref)}]` : ""));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-lg font-semibold tracking-tight">{block.title}</h3>
        {ai ? <Badge tone="ok">AI · grounded in {block.sources.length} source{block.sources.length === 1 ? "" : "s"}</Badge> : <Badge>Curated notes</Badge>}
        {block.provider === "rag-mock" && <Badge tone="info">Mock AI</Badge>}
      </div>
      <Prose text={body} />
      {note && <p className="text-2xs text-muted">{note}</p>}
      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3 text-xs text-muted">
        <span>Sources:</span>
        {block.sources.map((s, i) => <Badge key={s.document_id} tone="info">{ai ? `[${i + 1}] ` : ""}{s.title}</Badge>)}
      </div>
    </div>
  );
}
