"use client";

import { useRef, useState } from "react";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, Field, Input, PageHeader, Select, SkeletonRows, Table, Td, Textarea, Th } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { Company, Topic } from "@/lib/types";
import { useApi } from "@/lib/useApi";

interface Source { source: string; title: string; kind: string; source_uri: string; topic: string | null; company: string | null; chunks: number; embedded: number; created_at: string }
const KINDS = ["notes", "explanation", "worked_example", "company_prep", "interview_faq", "placement_notes"];

export default function KnowledgePage() {
  const sources = useApi<Source[]>("/kb/sources");
  const topics = useApi<Topic[]>("/topics");
  const companies = useApi<Company[]>("/companies");
  const [form, setForm] = useState({ title: "", kind: "notes", text: "", topic_id: "", company_id: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<{ id: number; title: string; score: number; topic: string | null; snippet: string }[] | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refs = { topic_id: form.topic_id ? Number(form.topic_id) : null, company_id: form.company_id ? Number(form.company_id) : null };

  async function act(key: string, fn: () => Promise<unknown>) {
    setBusy(key); setError(null);
    try { await fn(); await sources.reload(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Failed"); }
    finally { setBusy(null); }
  }

  const addText = (e: React.FormEvent) => { e.preventDefault(); void act("add", async () => {
    await api("/kb/documents", { method: "POST", json: { title: form.title, kind: form.kind, text: form.text, ...refs } });
    setForm({ ...form, title: "", text: "" });
  }); };

  const addFile = (f?: File) => f && act("file", async () => {
    const fd = new FormData();
    fd.append("file", f); fd.append("title", form.title || f.name); fd.append("kind", form.kind);
    if (refs.topic_id) fd.append("topic_id", String(refs.topic_id));
    if (refs.company_id) fd.append("company_id", String(refs.company_id));
    await api("/kb/documents/upload", { method: "POST", body: fd });
    if (fileRef.current) fileRef.current.value = "";
  });

  const pending = (sources.data ?? []).some((s) => s.embedded < s.chunks);

  return (
    <div className="space-y-5">
      <PageHeader title="Knowledge base" description="Material the AI tutor retrieves from (pgvector). Documents are chunked and embedded in the background." />
      {error && <ErrorState message={error} />}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Add material" description="Paste text, or upload .txt / .md / .pdf" />
          <form onSubmit={addText} className="space-y-3 p-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Title"><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
              <Field label="Kind"><Select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>{KINDS.map((k) => <option key={k} value={k}>{k.replaceAll("_", " ")}</option>)}</Select></Field>
              <Field label="Topic (optional)"><Select value={form.topic_id} onChange={(e) => setForm({ ...form, topic_id: e.target.value })}><option value="">—</option>{(topics.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.area} · {t.name}</option>)}</Select></Field>
              <Field label="Company (optional)"><Select value={form.company_id} onChange={(e) => setForm({ ...form, company_id: e.target.value })}><option value="">—</option>{(companies.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
            </div>
            <Field label="Text"><Textarea rows={6} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} /></Field>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" loading={busy === "add"} disabled={form.title.length < 3 || form.text.length < 20}>Add text</Button>
              <input ref={fileRef} type="file" accept=".txt,.md,.pdf" className="hidden" onChange={(e) => addFile(e.target.files?.[0])} />
              <Button type="button" variant="secondary" loading={busy === "file"} onClick={() => fileRef.current?.click()}>Upload file</Button>
            </div>
          </form>
        </Card>
        <Card>
          <CardHeader title="Test retrieval" description="See what the tutor would retrieve for a query (no LLM call)." />
          <form className="flex gap-2 p-4" onSubmit={async (e) => { e.preventDefault(); setError(null); try { setHits(await api("/kb/search", { method: "POST", json: { query, k: 5 } })); } catch (err) { setError(err instanceof ApiError ? err.message : "Search failed"); } }}>
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. why is BFS shortest path" />
            <Button type="submit" variant="secondary">Search</Button>
          </form>
          <div className="space-y-2 px-4 pb-4">
            {hits?.length === 0 && <p className="text-sm text-muted">No chunk passed the relevance threshold.</p>}
            {hits?.map((h) => (
              <div key={h.id} className="rounded-md border border-border p-2 text-xs">
                <div className="flex items-center gap-2"><span className="font-medium">{h.title}</span>{h.topic && <Badge>{h.topic}</Badge>}<span className="tabular ml-auto text-muted">{h.score.toFixed(3)}</span></div>
                <p className="mt-1 text-text-2">{h.snippet}…</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Documents" description={pending ? "Some chunks are still being embedded — refresh in a moment." : undefined}
          actions={<>
            <Button size="sm" variant="ghost" onClick={sources.reload}>Refresh</Button>
            <Button size="sm" variant="secondary" loading={busy === "reembed"} onClick={() => confirm("Re-embed every chunk? (needed after changing the embedding model)") && act("reembed", () => api("/kb/reembed?all_documents=true", { method: "POST" }))}>Re-embed all</Button>
          </>} />
        {sources.loading && !sources.data ? <SkeletonRows rows={5} cols={4} /> : !sources.data?.length ? <EmptyState title="Empty knowledge base" /> : (
          <Table>
            <thead><tr><Th>Title</Th><Th>Kind</Th><Th>Tags</Th><Th className="text-right">Chunks</Th><Th>Embedded</Th><Th>Added</Th><Th /></tr></thead>
            <tbody>
              {sources.data.map((s) => (
                <tr key={s.source}>
                  <Td className="font-medium">{s.title}</Td>
                  <Td className="text-xs text-text-2">{s.kind.replaceAll("_", " ")}</Td>
                  <Td><div className="flex gap-1">{s.topic && <Badge tone="accent">{s.topic}</Badge>}{s.company && <Badge tone="ochre">{s.company}</Badge>}</div></Td>
                  <Td className="tabular text-right">{s.chunks}</Td>
                  <Td>{s.embedded === s.chunks ? <Badge tone="ok">✓</Badge> : <Badge tone="warn">{s.embedded}/{s.chunks}</Badge>}</Td>
                  <Td className="text-xs text-muted">{fmtDate(s.created_at)}</Td>
                  <Td className="text-right"><Button size="sm" variant="ghost" className="text-danger" onClick={() => confirm(`Delete “${s.title}”?`) && act(`del-${s.source}`, () => api(`/kb/sources/${s.source}`, { method: "DELETE" }))}>Delete</Button></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
