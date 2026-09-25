"use client";

import { useDeferredValue, useState } from "react";
import { QuestionFilters, useFilterString } from "@/components/QuestionFilters";
import { QuestionTable } from "@/components/QuestionTable";
import { Button, Card, ErrorState, Field, Input, Modal, PageHeader, Select, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { Company, Difficulty, Question, QuestionType, Topic } from "@/lib/types";
import { QUESTION_TYPES, TYPE_LABEL } from "@/lib/types";
import { useApi } from "@/lib/useApi";

type Opt = { id: string; text: string };
type Sample = { input: string; output: string };

interface Draft {
  id?: number;
  type: QuestionType;
  title: string;
  body: string;
  difficulty: Difficulty;
  topic_id: number | null;
  company_ids: number[];
  status: Question["status"];
  explanation: string;
  options: Opt[];
  correct: string[];
  value: string;
  tolerance: string;
  code: string;
  language: string;
  expected_output: string;
  constraints: string;
  input_format: string;
  output_format: string;
  samples: Sample[];
  hidden_tests: Sample[];
  schema_sql: string;
  reference_query: string;
  fix: string;
  key_points: string;
}

const LETTERS = "abcdefgh";

function blank(): Draft {
  return {
    type: "mcq", title: "", body: "", difficulty: "easy", topic_id: null, company_ids: [], status: "draft", explanation: "",
    options: [{ id: "a", text: "" }, { id: "b", text: "" }], correct: [], value: "", tolerance: "0",
    code: "", language: "python", expected_output: "", constraints: "", input_format: "", output_format: "",
    samples: [{ input: "", output: "" }], hidden_tests: [{ input: "", output: "" }], schema_sql: "", reference_query: "", fix: "", key_points: "",
  };
}

function fromQuestion(q: Question): Draft {
  const a = (q.answer ?? {}) as Record<string, unknown>;
  const m = q.meta as Record<string, unknown>;
  const d = blank();
  return {
    ...d, id: q.id, type: q.type, title: q.title, body: q.body, difficulty: q.difficulty, topic_id: q.topic?.id ?? null,
    company_ids: q.companies.map((c) => c.id), status: q.status, explanation: q.explanation ?? "",
    options: q.options.length ? q.options : d.options, correct: (a.correct as string[]) ?? [],
    value: a.value != null ? String(a.value) : "", tolerance: a.tolerance != null ? String(a.tolerance) : "0",
    code: (m.code as string) ?? "", language: (m.language as string) ?? "python", expected_output: (a.expected_output as string) ?? "",
    constraints: (m.constraints as string) ?? "", input_format: (m.input_format as string) ?? "", output_format: (m.output_format as string) ?? "",
    samples: (m.samples as Sample[]) ?? d.samples, hidden_tests: (a.hidden_tests as Sample[]) ?? d.hidden_tests,
    schema_sql: (m.schema_sql as string) ?? "", reference_query: (a.reference_query as string) ?? "",
    fix: (a.fix as string) ?? "", key_points: ((a.key_points as string[]) ?? []).join("\n"),
  };
}

function toPayload(d: Draft) {
  let options: Opt[] = [];
  let answer: Record<string, unknown> = {};
  let meta: Record<string, unknown> = {};
  switch (d.type) {
    case "mcq":
    case "multi_select":
      options = d.options;
      answer = { correct: d.correct };
      break;
    case "numerical":
      answer = { value: Number(d.value), tolerance: Number(d.tolerance || 0) };
      break;
    case "output_prediction":
      meta = { code: d.code, language: d.language };
      answer = { expected_output: d.expected_output };
      break;
    case "coding":
      meta = { constraints: d.constraints, input_format: d.input_format, output_format: d.output_format, samples: d.samples.filter((s) => s.input || s.output) };
      answer = { hidden_tests: d.hidden_tests.filter((s) => s.input || s.output) };
      break;
    case "sql":
      meta = { schema_sql: d.schema_sql };
      answer = { reference_query: d.reference_query };
      break;
    case "debugging":
      meta = { code: d.code, language: d.language };
      answer = { fix: d.fix };
      break;
    case "theory":
      answer = { key_points: d.key_points.split("\n").map((s) => s.trim()).filter(Boolean) };
      break;
  }
  return {
    type: d.type, title: d.title, body: d.body, difficulty: d.difficulty, topic_id: d.topic_id, company_ids: d.company_ids,
    status: d.status, explanation: d.explanation, options, answer, meta,
  };
}

function PairsEditor({ label, rows, onChange }: { label: string; rows: Sample[]; onChange: (r: Sample[]) => void }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs font-medium text-text-2">
        {label}
        <Button size="sm" variant="ghost" type="button" onClick={() => onChange([...rows, { input: "", output: "" }])}>+ Add</Button>
      </div>
      {rows.map((r, i) => (
        <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2">
          <Textarea rows={2} className="font-mono text-xs" placeholder="input" value={r.input} onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, input: e.target.value } : x)))} />
          <Textarea rows={2} className="font-mono text-xs" placeholder="expected output" value={r.output} onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, output: e.target.value } : x)))} />
          <Button size="sm" variant="ghost" type="button" aria-label="Remove" disabled={rows.length <= 1} onClick={() => onChange(rows.filter((_, j) => j !== i))}>✕</Button>
        </div>
      ))}
    </div>
  );
}

function TypeFields({ d, set }: { d: Draft; set: (p: Partial<Draft>) => void }) {
  const codeField = (
    <div className="grid gap-3 sm:grid-cols-[1fr_140px]">
      <Field label="Code snippet"><Textarea rows={7} className="font-mono text-xs" value={d.code} onChange={(e) => set({ code: e.target.value })} /></Field>
      <Field label="Language">
        <Select value={d.language} onChange={(e) => set({ language: e.target.value })}>
          <option value="python">Python</option><option value="cpp">C++</option><option value="java">Java</option><option value="javascript">JavaScript</option>
        </Select>
      </Field>
    </div>
  );

  switch (d.type) {
    case "mcq":
    case "multi_select": {
      const multi = d.type === "multi_select";
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-medium text-text-2">
            Options — mark {multi ? "all correct answers" : "the correct answer"}
            <Button size="sm" variant="ghost" type="button" disabled={d.options.length >= 8}
              onClick={() => set({ options: [...d.options, { id: LETTERS[d.options.length], text: "" }] })}>+ Option</Button>
          </div>
          {d.options.map((o, i) => (
            <div key={o.id} className="flex items-center gap-2">
              <input type={multi ? "checkbox" : "radio"} name="correct" aria-label={`Option ${o.id} correct`} className="accent-[var(--accent)]"
                checked={d.correct.includes(o.id)}
                onChange={(e) => set({ correct: multi ? (e.target.checked ? [...d.correct, o.id] : d.correct.filter((c) => c !== o.id)) : [o.id] })} />
              <span className="w-4 font-mono text-xs uppercase text-muted">{o.id}</span>
              <Input value={o.text} onChange={(e) => set({ options: d.options.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)) })} />
              <Button size="sm" variant="ghost" type="button" disabled={d.options.length <= 2} aria-label="Remove option"
                onClick={() => {
                  const opts = d.options.filter((_, j) => j !== i).map((x, j) => ({ ...x, id: LETTERS[j] }));
                  set({ options: opts, correct: [] });
                }}>✕</Button>
            </div>
          ))}
        </div>
      );
    }
    case "numerical":
      return (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Correct value"><Input type="number" step="any" value={d.value} onChange={(e) => set({ value: e.target.value })} /></Field>
          <Field label="Tolerance (±)"><Input type="number" step="any" min={0} value={d.tolerance} onChange={(e) => set({ tolerance: e.target.value })} /></Field>
        </div>
      );
    case "output_prediction":
      return (
        <div className="space-y-3">
          {codeField}
          <Field label="Expected output"><Textarea rows={2} className="font-mono text-xs" value={d.expected_output} onChange={(e) => set({ expected_output: e.target.value })} /></Field>
        </div>
      );
    case "coding":
      return (
        <div className="space-y-3">
          <Field label="Constraints"><Textarea rows={2} value={d.constraints} onChange={(e) => set({ constraints: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Input format"><Textarea rows={2} value={d.input_format} onChange={(e) => set({ input_format: e.target.value })} /></Field>
            <Field label="Output format"><Textarea rows={2} value={d.output_format} onChange={(e) => set({ output_format: e.target.value })} /></Field>
          </div>
          <PairsEditor label="Visible sample tests (shown to students)" rows={d.samples} onChange={(samples) => set({ samples })} />
          <PairsEditor label="Hidden tests (never sent to students; used by Judge0 in Phase 3)" rows={d.hidden_tests} onChange={(hidden_tests) => set({ hidden_tests })} />
        </div>
      );
    case "sql":
      return (
        <div className="space-y-3">
          <Field label="Schema (DDL)"><Textarea rows={4} className="font-mono text-xs" value={d.schema_sql} onChange={(e) => set({ schema_sql: e.target.value })} /></Field>
          <Field label="Reference query"><Textarea rows={3} className="font-mono text-xs" value={d.reference_query} onChange={(e) => set({ reference_query: e.target.value })} /></Field>
        </div>
      );
    case "debugging":
      return (
        <div className="space-y-3">
          {codeField}
          <Field label="Expected fix"><Input value={d.fix} onChange={(e) => set({ fix: e.target.value })} /></Field>
        </div>
      );
    case "theory":
      return <Field label="Key points expected in a good answer" hint="One per line"><Textarea rows={4} value={d.key_points} onChange={(e) => set({ key_points: e.target.value })} /></Field>;
  }
}

export default function QuestionsAdmin() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const filter = useFilterString(useDeferredValue(filters));
  const [version, setVersion] = useState(0);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const topics = useApi<Topic[]>("/topics");
  const companies = useApi<Company[]>("/companies");

  const set = (p: Partial<Draft>) => setDraft((d) => (d ? { ...d, ...p } : d));

  async function save() {
    if (!draft) return;
    setSaving(true);
    setFormError(null);
    try {
      await api(draft.id ? `/questions/${draft.id}` : "/questions", { method: draft.id ? "PATCH" : "POST", json: toPayload(draft) });
      setDraft(null);
      setVersion((v) => v + 1);
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!draft?.id || !confirm("Delete this question permanently?")) return;
    await api(`/questions/${draft.id}`, { method: "DELETE" }).catch(() => undefined);
    setDraft(null);
    setVersion((v) => v + 1);
  }

  return (
    <div>
      <PageHeader title="Questions" description="All 8 question types. Only published questions are visible to students."
        actions={<Button onClick={() => { setFormError(null); setDraft(blank()); }}>New question</Button>} />
      <Card>
        <QuestionFilters value={filters} onChange={setFilters} withStatus />
        <QuestionTable key={`${filter}-${version}`} filter={filter} admin onEdit={(q) => { setFormError(null); setDraft(fromQuestion(q)); }} />
      </Card>

      <Modal wide open={!!draft} onClose={() => setDraft(null)} title={draft?.id ? "Edit question" : "New question"}
        footer={<>
          {draft?.id && <Button variant="ghost" className="mr-auto text-danger" onClick={remove}>Delete</Button>}
          <Button variant="secondary" onClick={() => setDraft(null)}>Cancel</Button>
          <Button onClick={save} loading={saving}>Save</Button>
        </>}>
        {draft && (
          <div className="space-y-4">
            {formError && <ErrorState message={formError} />}
            <div className="grid gap-3 sm:grid-cols-4">
              <Field label="Type">
                <Select value={draft.type} onChange={(e) => set({ type: e.target.value as QuestionType, correct: [] })}>
                  {QUESTION_TYPES.map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
                </Select>
              </Field>
              <Field label="Difficulty">
                <Select value={draft.difficulty} onChange={(e) => set({ difficulty: e.target.value as Difficulty })}>
                  <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
                </Select>
              </Field>
              <Field label="Topic">
                <Select value={draft.topic_id ?? ""} onChange={(e) => set({ topic_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">— none —</option>
                  {(topics.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.area} · {t.name}</option>)}
                </Select>
              </Field>
              <Field label="Status">
                <Select value={draft.status} onChange={(e) => set({ status: e.target.value as Draft["status"] })}>
                  <option value="draft">Draft</option><option value="published">Published</option><option value="archived">Archived</option>
                </Select>
              </Field>
            </div>
            <Field label="Title"><Input value={draft.title} onChange={(e) => set({ title: e.target.value })} /></Field>
            <Field label="Statement"><Textarea rows={4} value={draft.body} onChange={(e) => set({ body: e.target.value })} /></Field>

            <div className="rounded-md border border-border bg-surface-2/50 p-3"><TypeFields d={draft} set={set} /></div>

            <Field label="Company tags" hint="Shown to students as observed patterns, not official specifications.">
              <div className="flex flex-wrap gap-1.5">
                {(companies.data ?? []).map((c) => {
                  const on = draft.company_ids.includes(c.id);
                  return (
                    <button type="button" key={c.id} aria-pressed={on}
                      onClick={() => set({ company_ids: on ? draft.company_ids.filter((x) => x !== c.id) : [...draft.company_ids, c.id] })}
                      className={`h-7 rounded-md border px-2.5 text-xs font-medium ${on ? "border-ochre bg-ochre-soft text-ochre" : "border-border text-text-2 hover:bg-surface-2"}`}>
                      {c.name}
                    </button>
                  );
                })}
              </div>
            </Field>
            <Field label="Explanation" hint="Revealed to students only after they attempt the question (Phase 2).">
              <Textarea rows={3} value={draft.explanation} onChange={(e) => set({ explanation: e.target.value })} />
            </Field>
          </div>
        )}
      </Modal>
    </div>
  );
}
