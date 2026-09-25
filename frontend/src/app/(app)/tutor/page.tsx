"use client";

import clsx from "clsx";
import { useState } from "react";
import { Citations, CitedText, GroundingBar } from "@/components/ai";
import { Badge, Button, Card, ErrorState, Field, Input, PageHeader, Select, Skeleton, Textarea } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { AIEnvelope, Company, Page, Question, Topic } from "@/lib/types";
import { useApi } from "@/lib/useApi";

type Mode = "explain" | "hint" | "interviewer" | "evaluate" | "followup" | "revision";
const MODES: { key: Mode; label: string; blurb: string }[] = [
  { key: "explain", label: "Explain", blurb: "A grounded, beginner-level explanation of a concept, with sources." },
  { key: "hint", label: "Hint", blurb: "A nudge on a specific question. Never the answer — enforced, not just requested." },
  { key: "interviewer", label: "Interviewer", blurb: "An interview question matched to a company's observed pattern and difficulty." },
  { key: "evaluate", label: "Evaluate", blurb: "Score a free-text answer against expected concepts (interpretive, not a grade)." },
  { key: "followup", label: "Follow-up", blurb: "A deeper question built on your previous exchange." },
  { key: "revision", label: "Revision", blurb: "Fresh practice on the items you previously got wrong." },
];

function List({ title, items, tone }: { title: string; items: string[]; tone?: "ok" | "danger" }) {
  if (!items?.length) return null;
  return (
    <div>
      <div className="mb-1 text-2xs font-semibold uppercase tracking-wide text-muted">{title}</div>
      <div className="flex flex-wrap gap-1.5">{items.map((x) => <Badge key={x} tone={tone ?? "neutral"}>{x}</Badge>)}</div>
    </div>
  );
}

function Result({ env }: { env: AIEnvelope }) {
  const d = env.data as Record<string, unknown>;
  const text = (k: string) => String(d[k] ?? "");
  return (
    <Card className="space-y-4 p-5">
      <GroundingBar env={env} />
      {env.mode === "explain" && (<>
        <CitedText text={text("explanation")} citations={env.citations} />
        <List title="Key points" items={d.key_points as string[]} />
        {text("example") && <div className="rounded-md bg-surface-2 p-3 text-sm"><span className="font-medium">Example. </span>{text("example")}</div>}
      </>)}
      {env.mode === "hint" && (<>
        <p className="text-base leading-relaxed">{text("hint")}</p>
        <p className="text-sm text-text-2"><span className="font-medium">Next step: </span>{text("next_step")}</p>
        <p className="text-2xs text-muted">Leak check: {env.checks.hint_leak === "pass" ? "passed — the answer isn't in this hint" : "the model's hint revealed the answer, so a safe generic hint is shown instead"}</p>
      </>)}
      {env.mode === "interviewer" && (<>
        <p className="text-lg font-medium leading-relaxed">{text("question")}</p>
        <List title="A strong answer covers" items={d.expected_concepts as string[]} />
        <List title="Likely follow-ups" items={d.follow_up_areas as string[]} />
      </>)}
      {env.mode === "evaluate" && (<>
        <div className="flex items-baseline gap-2"><span className="tabular text-4xl font-semibold">{String(d.score)}</span><span className="text-muted">/ 10</span>
          <span className="text-2xs text-muted">AI interpretation — not used in any score</span></div>
        <List title="Covered" items={d.covered_concepts as string[]} tone="ok" />
        <List title="Missing" items={d.missing_concepts as string[]} tone="danger" />
        <p className="text-sm leading-relaxed">{text("feedback")}</p>
      </>)}
      {env.mode === "followup" && (<>
        <p className="text-lg font-medium leading-relaxed">{text("question")}</p>
        <p className="text-sm text-text-2">{text("why")}</p>
      </>)}
      {env.mode === "revision" && (
        <ol className="space-y-3">
          {(d.items as { question: string; answer: string; explanation: string }[]).map((it, i) => (
            <li key={i} className="rounded-md border border-border p-3">
              <p className="font-medium">{i + 1}. {it.question}</p>
              <details className="mt-2 text-sm"><summary className="cursor-pointer text-accent">Show answer</summary>
                <p className="mt-1"><span className="font-medium">{it.answer}</span> — {it.explanation}</p></details>
            </li>
          ))}
        </ol>
      )}
      <Citations items={env.citations} />
    </Card>
  );
}

export default function TutorPage() {
  const [mode, setMode] = useState<Mode>("explain");
  const [form, setForm] = useState<Record<string, string>>({ difficulty: "medium" });
  const [env, setEnv] = useState<AIEnvelope | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const topics = useApi<Topic[]>("/topics");
  const companies = useApi<Company[]>("/companies");
  const questions = useApi<Page<Question>>("/questions?page_size=100");
  const status = useApi<{ mock: boolean; fast_model: string; strong_model: string }>("/ai/status");

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const num = (k: string) => (form[k] ? Number(form[k]) : null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null); setEnv(null);
    const body: Record<Mode, unknown> = {
      explain: { question: form.question, topic_id: num("topic_id") },
      hint: { question_id: num("question_id"), attempt: form.attempt || null },
      interviewer: { company_id: num("company_id"), topic_id: num("topic_id"), difficulty: form.difficulty },
      evaluate: { question: form.question, answer: form.answer, expected_concepts: form.concepts ? form.concepts.split(",").map((s) => s.trim()).filter(Boolean) : null },
      followup: { previous_question: form.question, previous_answer: form.answer, topic_id: num("topic_id") },
      revision: {},
    };
    try {
      setEnv(await api<AIEnvelope>(`/ai/tutor/${mode}`, { method: "POST", json: body[mode] }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Tutor unavailable");
    } finally { setBusy(false); }
  }

  const topicSelect = (
    <Field label="Topic (optional — narrows retrieval)">
      <Select value={form.topic_id ?? ""} onChange={(e) => set("topic_id", e.target.value)}>
        <option value="">Any topic</option>
        {(topics.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.area} · {t.name}</option>)}
      </Select>
    </Field>
  );

  return (
    <div className="space-y-5">
      <PageHeader title="AI tutor"
        description="Six bounded modes. Answers are grounded in the course knowledge base and cite their sources; the tutor never grades code or decides readiness."
        actions={status.data && <Badge tone={status.data.mock ? "info" : "ok"}>{status.data.mock ? "Mock mode" : `Gemini · ${status.data.fast_model}`}</Badge>} />

      <div className="flex flex-wrap gap-1 rounded-lg border border-border bg-surface p-1" role="tablist">
        {MODES.map((m) => (
          <button key={m.key} role="tab" aria-selected={mode === m.key} onClick={() => { setMode(m.key); setEnv(null); setError(null); }}
            className={clsx("h-8 rounded-md px-3 text-sm", mode === m.key ? "bg-accent text-accent-fg" : "text-text-2 hover:bg-surface-2")}>{m.label}</button>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <Card className="h-fit p-5">
          <p className="mb-4 text-sm text-muted">{MODES.find((m) => m.key === mode)!.blurb}</p>
          <form onSubmit={run} className="space-y-3">
            {mode === "explain" && (<>
              <Field label="What do you want explained?"><Textarea rows={3} required value={form.question ?? ""} onChange={(e) => set("question", e.target.value)} placeholder="Why does BFS find shortest paths in unweighted graphs?" /></Field>
              {topicSelect}
            </>)}
            {mode === "hint" && (<>
              <Field label="Question">
                <Select required value={form.question_id ?? ""} onChange={(e) => set("question_id", e.target.value)}>
                  <option value="">Choose a question…</option>
                  {(questions.data?.items ?? []).map((q) => <option key={q.id} value={q.id}>{q.title}</option>)}
                </Select>
              </Field>
              <Field label="Your attempt so far (optional)"><Textarea rows={4} value={form.attempt ?? ""} onChange={(e) => set("attempt", e.target.value)} /></Field>
            </>)}
            {mode === "interviewer" && (<>
              <Field label="Company (optional)">
                <Select value={form.company_id ?? ""} onChange={(e) => set("company_id", e.target.value)}>
                  <option value="">Generic</option>
                  {(companies.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </Field>
              {topicSelect}
              <Field label="Difficulty">
                <Select value={form.difficulty} onChange={(e) => set("difficulty", e.target.value)}>
                  <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
                </Select>
              </Field>
            </>)}
            {(mode === "evaluate" || mode === "followup") && (<>
              <Field label={mode === "evaluate" ? "Question" : "Previous question"}><Textarea rows={2} required value={form.question ?? ""} onChange={(e) => set("question", e.target.value)} /></Field>
              <Field label={mode === "evaluate" ? "Your answer" : "Your previous answer"}><Textarea rows={5} required value={form.answer ?? ""} onChange={(e) => set("answer", e.target.value)} /></Field>
              {mode === "evaluate" ? <Field label="Expected concepts (optional, comma-separated)"><Input value={form.concepts ?? ""} onChange={(e) => set("concepts", e.target.value)} /></Field> : topicSelect}
            </>)}
            {mode === "revision" && <p className="text-sm text-text-2">Uses your most recent incorrect answers (tests, study and judged code) to write new practice on the same concepts.</p>}
            <Button type="submit" loading={busy} className="w-full">{mode === "revision" ? "Generate revision set" : "Ask the tutor"}</Button>
          </form>
        </Card>
        <div>
          {error && <ErrorState message={error} />}
          {busy && <Card className="space-y-3 p-5"><Skeleton className="h-4 w-40" /><Skeleton className="h-20 w-full" /><Skeleton className="h-10 w-2/3" /></Card>}
          {env && <Result env={env} />}
          {!env && !busy && !error && <Card className="p-8 text-center text-sm text-muted">Answers appear here with their grounding status and sources.</Card>}
        </div>
      </div>
    </div>
  );
}
