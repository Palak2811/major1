"use client";

import { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Select, SkeletonRows, Table, Td, Textarea, Th } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtDuration } from "@/lib/format";
import type { Company, QuestionType, TestSummary, Topic } from "@/lib/types";
import { QUESTION_TYPES, TYPE_LABEL } from "@/lib/types";
import { useApi } from "@/lib/useApi";

interface SectionDraft { name: string; minutes: number; topic_ids: number[]; count: number; types: QuestionType[]; marks: number }
interface Draft {
  title: string; description: string; company_id: number | null; negative_marking: boolean; negative_ratio: number;
  randomize: boolean; is_published: boolean; mix: { easy: number; medium: number; hard: number }; sections: SectionDraft[];
}

const blankSection = (n: number): SectionDraft => ({ name: `Section ${n}`, minutes: 15, topic_ids: [], count: 5, types: ["mcq", "multi_select", "numerical"], marks: 1 });
const blank = (): Draft => ({
  title: "", description: "", company_id: null, negative_marking: true, negative_ratio: 0.25, randomize: true, is_published: false,
  mix: { easy: 30, medium: 50, hard: 20 }, sections: [blankSection(1)],
});

export default function TestsAdmin() {
  const tests = useApi<TestSummary[]>("/tests");
  const topics = useApi<Topic[]>("/topics");
  const companies = useApi<Company[]>("/companies");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const setSec = (i: number, patch: Partial<SectionDraft>) =>
    setDraft((d) => d && { ...d, sections: d.sections.map((s, j) => (j === i ? { ...s, ...patch } : s)) });

  async function compose() {
    if (!draft) return;
    setSaving(true);
    setFormError(null);
    try {
      await api("/tests/compose", {
        method: "POST",
        json: {
          title: draft.title, description: draft.description, company_id: draft.company_id,
          negative_marking: draft.negative_marking, negative_ratio: draft.negative_ratio,
          randomize: draft.randomize, is_published: draft.is_published,
          mix: { easy: draft.mix.easy / 100, medium: draft.mix.medium / 100, hard: draft.mix.hard / 100 },
          sections: draft.sections.map((s) => ({
            name: s.name, time_limit_seconds: s.minutes * 60, topic_ids: s.topic_ids, count: s.count, types: s.types, marks: s.marks,
          })),
        },
      });
      setDraft(null);
      await tests.reload();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Could not compose test");
    } finally {
      setSaving(false);
    }
  }

  async function togglePublish(t: TestSummary) {
    await api(`/tests/${t.id}`, { method: "PATCH", json: { is_published: !t.is_published } }).catch(() => undefined);
    await tests.reload();
  }

  async function remove(t: TestSummary) {
    if (!confirm(`Delete “${t.title}”? Attempt history for it will show as a deleted test.`)) return;
    await api(`/tests/${t.id}`, { method: "DELETE" }).catch(() => undefined);
    await tests.reload();
  }

  const mixTotal = draft ? draft.mix.easy + draft.mix.medium + draft.mix.hard : 0;
  const canSave = draft && draft.title.trim().length >= 3 && mixTotal > 0 && draft.sections.every((s) => s.topic_ids.length && s.count > 0 && s.name.trim());

  return (
    <div>
      <PageHeader title="Tests" description="Compose sectioned tests from topic pools with a balanced difficulty mix."
        actions={<Button onClick={() => { setFormError(null); setDraft(blank()); }}>Compose test</Button>} />
      <Card>
        {tests.error ? <div className="p-4"><ErrorState message={tests.error.message} onRetry={tests.reload} /></div> :
          tests.loading && !tests.data ? <SkeletonRows rows={3} cols={4} /> :
            !tests.data?.length ? <EmptyState title="No tests yet" /> : (
              <Table>
                <thead><tr><Th>Title</Th><Th>Sections</Th><Th className="text-right">Questions</Th><Th className="text-right">Time</Th><Th>Status</Th><Th /></tr></thead>
                <tbody>
                  {tests.data.map((t) => (
                    <tr key={t.id}>
                      <Td className="font-medium">{t.title}{t.negative_marking && <Badge tone="danger" className="ml-2">−ve</Badge>}</Td>
                      <Td className="text-xs text-text-2">{t.sections.map((s) => s.name).join(", ")}</Td>
                      <Td className="tabular text-right">{t.question_count}</Td>
                      <Td className="tabular text-right text-text-2">{fmtDuration(t.duration_seconds * 1000)}</Td>
                      <Td>{t.is_published ? <Badge tone="ok">Published</Badge> : <Badge>Draft</Badge>}</Td>
                      <Td className="text-right">
                        <Button size="sm" variant="ghost" onClick={() => togglePublish(t)}>{t.is_published ? "Unpublish" : "Publish"}</Button>
                        <Button size="sm" variant="ghost" className="text-danger" onClick={() => remove(t)}>Delete</Button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
      </Card>

      <Modal wide open={!!draft} onClose={() => setDraft(null)} title="Compose test"
        footer={<><Button variant="secondary" onClick={() => setDraft(null)}>Cancel</Button><Button onClick={compose} loading={saving} disabled={!canSave}>Compose</Button></>}>
        {draft && (
          <div className="space-y-4">
            {formError && <ErrorState message={formError} />}
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-2"><Field label="Title"><Input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></Field></div>
              <Field label="Company (optional)">
                <Select value={draft.company_id ?? ""} onChange={(e) => setDraft({ ...draft, company_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">— none —</option>
                  {(companies.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </Field>
            </div>
            <Field label="Description"><Textarea rows={2} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></Field>

            <div className="grid gap-3 sm:grid-cols-4">
              {(["easy", "medium", "hard"] as const).map((k) => (
                <Field key={k} label={`${k[0].toUpperCase()}${k.slice(1)} %`}>
                  <Input type="number" min={0} max={100} value={draft.mix[k]} onChange={(e) => setDraft({ ...draft, mix: { ...draft.mix, [k]: Number(e.target.value) || 0 } })} />
                </Field>
              ))}
              <Field label="Negative marks (× marks)">
                <Input type="number" min={0} max={1} step={0.05} disabled={!draft.negative_marking} value={draft.negative_ratio}
                  onChange={(e) => setDraft({ ...draft, negative_ratio: Number(e.target.value) })} />
              </Field>
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
              {([["negative_marking", "Negative marking"], ["randomize", "Randomise order per attempt"], ["is_published", "Publish immediately"]] as const).map(([k, l]) => (
                <label key={k} className="flex items-center gap-2">
                  <input type="checkbox" className="accent-[var(--accent)]" checked={draft[k]} onChange={(e) => setDraft({ ...draft, [k]: e.target.checked })} />{l}
                </label>
              ))}
            </div>

            {draft.sections.map((s, i) => (
              <fieldset key={i} className="space-y-3 rounded-md border border-border p-3">
                <legend className="px-1 text-xs font-semibold text-text-2">Section {i + 1}</legend>
                <div className="grid gap-3 sm:grid-cols-4">
                  <Field label="Name"><Input value={s.name} onChange={(e) => setSec(i, { name: e.target.value })} /></Field>
                  <Field label="Time limit (min)"><Input type="number" min={1} value={s.minutes} onChange={(e) => setSec(i, { minutes: Math.max(1, Number(e.target.value) || 1) })} /></Field>
                  <Field label="Questions"><Input type="number" min={1} value={s.count} onChange={(e) => setSec(i, { count: Math.max(1, Number(e.target.value) || 1) })} /></Field>
                  <Field label="Marks each"><Input type="number" min={0.25} step={0.25} value={s.marks} onChange={(e) => setSec(i, { marks: Number(e.target.value) || 1 })} /></Field>
                </div>
                <Field label="Topics (includes sub-topics)" hint="Ctrl/Cmd-click to select several">
                  <Select multiple className="h-28 py-1" value={s.topic_ids.map(String)}
                    onChange={(e) => setSec(i, { topic_ids: Array.from(e.target.selectedOptions).map((o) => Number(o.value)) })}>
                    {(topics.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.area} · {t.name}</option>)}
                  </Select>
                </Field>
                <div>
                  <div className="mb-1 text-xs font-medium text-text-2">Question types</div>
                  <div className="flex flex-wrap gap-1.5">
                    {QUESTION_TYPES.map((t) => {
                      const on = s.types.includes(t);
                      return (
                        <button type="button" key={t} aria-pressed={on} onClick={() => setSec(i, { types: on ? s.types.filter((x) => x !== t) : [...s.types, t] })}
                          className={`h-7 rounded-md border px-2 text-xs ${on ? "border-accent bg-accent-soft text-accent" : "border-border text-text-2 hover:bg-surface-2"}`}>
                          {TYPE_LABEL[t]}
                        </button>
                      );
                    })}
                  </div>
                </div>
                {draft.sections.length > 1 && <Button size="sm" variant="ghost" className="text-danger" onClick={() => setDraft({ ...draft, sections: draft.sections.filter((_, j) => j !== i) })}>Remove section</Button>}
              </fieldset>
            ))}
            <Button variant="secondary" size="sm" onClick={() => setDraft({ ...draft, sections: [...draft.sections, blankSection(draft.sections.length + 1)] })}>+ Add section</Button>
          </div>
        )}
      </Modal>
    </div>
  );
}
