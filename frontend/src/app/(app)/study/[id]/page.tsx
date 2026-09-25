"use client";

import clsx from "clsx";
import Link from "next/link";
import { use, useEffect, useRef, useState } from "react";
import { AnswerInput, describeKey } from "@/components/AnswerInput";
import { MasteryBar } from "@/components/Mastery";
import { Prose, TeachingCard } from "@/components/Prose";
import { QuestionView } from "@/components/QuestionView";
import { Badge, Button, Card, DifficultyBadge, ErrorState, Input, Skeleton } from "@/components/ui";
import { GroundingBar } from "@/components/ai";
import { api, ApiError } from "@/lib/api";
import type { AIEnvelope, Answer, AnswerResult, Question, StudySession, TeachingBlock } from "@/lib/types";
import { useApi } from "@/lib/useApi";

type Step = "question" | "explanation" | "example" | "followup" | "quiz" | "confidence" | "done";
const STEPS: [Step, string][] = [
  ["question", "Question"], ["explanation", "Explanation"], ["example", "Worked example"],
  ["followup", "Follow-up"], ["quiz", "Mini quiz"], ["confidence", "Confidence"], ["done", "Skill update"],
];
const CONFIDENCE = ["Guessing", "Unsure", "Fairly sure", "Confident", "Certain"];

function initialStep(s: StudySession): Step {
  if (s.stage === "done") return "done";
  if (s.stage === "question") return "question";
  if (s.stage === "followup") return "explanation"; // resumed after answering: re-show teaching
  return s.stage;
}

function Feedback({ q, r }: { q: Question; r: AnswerResult }) {
  const key = describeKey(q, r.answer);
  return (
    <div className={clsx("space-y-2 rounded-md border px-3 py-2.5 text-sm",
      !r.gradable ? "border-border bg-surface-2" : r.correct ? "border-ok/40 bg-ok-soft" : "border-danger/40 bg-danger-soft")}>
      <div className="flex items-center gap-2 font-medium">
        {!r.gradable ? "Not scored" : r.correct ? <span className="text-ok">Correct</span> : <span className="text-danger">Not quite</span>}
        {r.judged_by === "heuristic" && <Badge tone="warn">Keyword heuristic</Badge>}
      </div>
      {key && !r.correct && <p className="text-text-2"><span className="text-muted">Answer: </span>{key}</p>}
      {r.explanation && <p className="text-text-2">{r.explanation}</p>}
      {r.feedback && <p className="text-xs text-muted">{r.feedback}</p>}
    </div>
  );
}

function QuestionBlock({ q, result, onSubmit, label }: {
  q: Question; result?: AnswerResult; onSubmit: (a: Answer, ms: number) => Promise<void>; label: string;
}) {
  const [value, setValue] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<AIEnvelope | null>(null);
  const [hintBusy, setHintBusy] = useState(false);
  const [hintErr, setHintErr] = useState<string | null>(null);
  async function askHint() {
    setHintBusy(true);
    setHintErr(null);
    try { setHint(await api<AIEnvelope>("/ai/tutor/hint", { method: "POST", json: { question_id: q.id } })); }
    catch (e) { setHintErr(e instanceof ApiError ? e.message : "Hint unavailable"); }
    finally { setHintBusy(false); }
  }
  const started = useRef(Date.now());
  useEffect(() => { started.current = Date.now(); setValue(null); setHint(null); }, [q.id]);
  const shown = result ? result.response : value;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-2xs font-semibold uppercase tracking-wider text-muted">{label}</span>
        <DifficultyBadge level={q.difficulty} />
      </div>
      <h2 className="text-lg font-semibold tracking-tight">{q.title}</h2>
      <QuestionView q={q} hideOptions hideTags />
      <AnswerInput q={q} value={shown} onChange={setValue} disabled={!!result} reveal={result ? result.answer : null} />
      {!result && hint && (
        <div className="space-y-1.5 rounded-md border border-info/30 bg-info-soft px-3 py-2.5 text-sm">
          <div className="font-medium text-info">Hint</div>
          <p>{String(hint.data.hint)}</p>
          <p className="text-text-2">{String(hint.data.next_step)}</p>
          <GroundingBar env={hint} />
        </div>
      )}
      {hintErr && <p className="text-xs text-danger">{hintErr}</p>}
      {result ? <Feedback q={q} r={result} /> : (
        <div className="flex justify-between gap-2">
          <Button variant="ghost" loading={hintBusy} disabled={!!hint} onClick={askHint}>{hint ? "Hint shown" : "Get a hint"}</Button>
          <Button loading={busy} disabled={!value || Object.keys(value).length === 0}
            onClick={async () => { setBusy(true); try { await onSubmit(value!, Date.now() - started.current); } finally { setBusy(false); } }}>
            Check answer
          </Button>
        </div>
      )}
    </div>
  );
}

export default function StudySessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error, setData, reload } = useApi<StudySession>(`/study/sessions/${id}`);
  const [step, setStep] = useState<Step | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [quizIdx, setQuizIdx] = useState(0);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [completing, setCompleting] = useState(false);
  type TeachState = { block: TeachingBlock | null; fallback: boolean; reason?: string } | "loading";
  const [teach, setTeach] = useState<Record<string, TeachState>>({});
  const [deeper, setDeeper] = useState<AIEnvelope | null>(null);
  const [deeperBusy, setDeeperBusy] = useState(false);
  const [ask, setAsk] = useState("");
  const [asked, setAsked] = useState<AIEnvelope | null>(null);
  const [askBusy, setAskBusy] = useState(false);

  const requested = useRef<Set<string>>(new Set());
  useEffect(() => {
    const kind = step === "explanation" ? "explanation" : step === "example" ? "worked_example" : null;
    if (!kind || !data || teach[kind] || requested.current.has(kind)) return;
    requested.current.add(kind); // guard against double effects (React dev mode)
    setTeach((t) => ({ ...t, [kind]: "loading" }));
    api<{ block: TeachingBlock | null; fallback: boolean; reason?: string }>(`/study/sessions/${data.id}/teach/${kind}`, { method: "POST" })
      .then((r) => setTeach((t) => ({ ...t, [kind]: r })))
      .catch(() => setTeach((t) => ({ ...t, [kind]: { block: null, fallback: true, reason: "AI unavailable" } })));
  }, [step, data, teach]);

  function teachView(kind: "explanation" | "worked_example", curated: TeachingBlock | null, empty: string) {
    const t = teach[kind];
    if (!t || t === "loading") {
      return (
        <div className="space-y-3" aria-busy="true">
          <div className="text-xs text-muted">Retrieving course sources and writing a grounded {kind === "explanation" ? "explanation" : "worked example"}…</div>
          <Skeleton className="h-5 w-48" /><Skeleton className="h-24 w-full" />
        </div>
      );
    }
    return <TeachingCard block={t.block ?? curated} fallback={empty} note={t.fallback ? `Showing curated notes: ${t.reason ?? "AI unavailable"}.` : undefined} />;
  }

  useEffect(() => {
    if (data && step === null) {
      setStep(initialStep(data));
      const firstOpen = data.quiz.findIndex((q) => !data.answers[String(q.id)]);
      setQuizIdx(firstOpen === -1 ? Math.max(0, data.quiz.length - 1) : firstOpen);
    }
  }, [data, step]);

  if (error) return <ErrorState message={error.status === 404 ? "Session not found" : error.message} onRetry={reload} />;
  if (!data || !step) return <div className="space-y-4"><Skeleton className="h-6 w-60" /><Skeleton className="h-72 w-full" /></div>;
  const s = data;

  async function answer(q: Question, a: Answer, ms: number) {
    setActionError(null);
    try {
      setData(await api<StudySession>(`/study/sessions/${s.id}/answer`, { method: "POST", json: { question_id: q.id, answer: a, time_taken_ms: ms } }));
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Could not submit");
    }
  }

  async function complete() {
    if (!confidence) return;
    setCompleting(true);
    setActionError(null);
    try {
      setData(await api<StudySession>(`/study/sessions/${s.id}/complete`, { method: "POST", json: { confidence } }));
      setStep("done");
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Could not complete");
    } finally {
      setCompleting(false);
    }
  }

  const res = (q: Question | null) => (q ? s.answers[String(q.id)] : undefined);
  const stepIndex = STEPS.findIndex(([k]) => k === step);
  const quizDone = s.quiz.every((q) => res(q));
  const next = (to: Step) => () => setStep(to);

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-xs text-muted"><Link href="/study" className="hover:text-text">Study</Link> / {s.topic?.area}</div>
          <h1 className="text-xl font-semibold tracking-tight">{s.topic?.name}</h1>
        </div>
        <div className="text-right text-xs text-muted">
          Mastery at start: <span className="tabular font-medium text-text">{s.mastery_before == null ? "new" : Math.round(s.mastery_before)}</span>
          <span className="mx-1.5">·</span>targeting <DifficultyBadge level={s.target_difficulty} />
        </div>
      </div>

      <ol className="flex gap-1" aria-label="Cycle progress">
        {STEPS.map(([k, label], i) => (
          <li key={k} className="flex-1">
            <div className={clsx("h-1 rounded-full", i < stepIndex ? "bg-accent" : i === stepIndex ? "bg-ochre" : "bg-surface-3")} />
            <div className={clsx("mt-1.5 hidden text-2xs sm:block", i === stepIndex ? "font-medium text-text" : "text-muted")}>{label}</div>
          </li>
        ))}
      </ol>

      {actionError && <ErrorState message={actionError} />}

      <Card className="p-5">
        {step === "question" && (
          <>
            <QuestionBlock label="Question" q={s.question} result={res(s.question)} onSubmit={(a, ms) => answer(s.question, a, ms)} />
            {res(s.question) && (
              <div className="mt-4 space-y-3">
                {deeper && (
                  <div className="space-y-1.5 rounded-md border border-border bg-surface-2 p-3 text-sm">
                    <div className="text-2xs font-semibold uppercase tracking-wide text-muted">Go deeper</div>
                    <p className="font-medium">{String(deeper.data.question)}</p>
                    <p className="text-text-2">{String(deeper.data.why)}</p>
                    <GroundingBar env={deeper} />
                  </div>
                )}
                <div className="flex justify-between gap-2">
                  <Button variant="ghost" loading={deeperBusy} disabled={!!deeper} onClick={async () => {
                    setDeeperBusy(true);
                    const r = res(s.question)!;
                    try {
                      setDeeper(await api<AIEnvelope>("/ai/tutor/followup", { method: "POST", json: {
                        previous_question: `${s.question.title}: ${s.question.body}`,
                        previous_answer: JSON.stringify(r.response) + (r.correct ? " (marked correct)" : " (marked incorrect)"),
                        topic_id: s.topic?.id } }));
                    } catch (e) { setActionError(e instanceof ApiError ? e.message : "Tutor unavailable"); }
                    finally { setDeeperBusy(false); }
                  }}>Go deeper (AI follow-up)</Button>
                  <Button onClick={next("explanation")}>Continue to explanation</Button>
                </div>
              </div>
            )}
          </>
        )}

        {step === "explanation" && (
          <>
            {teachView("explanation", s.explanation, "No explanation available for this topic yet — review the answer explanation.")}
            <form className="mt-5 flex gap-2 border-t border-border pt-4" onSubmit={async (e) => {
              e.preventDefault();
              if (!ask.trim()) return;
              setAskBusy(true);
              try { setAsked(await api<AIEnvelope>("/ai/tutor/explain", { method: "POST", json: { question: ask, topic_id: s.topic?.id } })); }
              catch (err) { setActionError(err instanceof ApiError ? err.message : "Tutor unavailable"); }
              finally { setAskBusy(false); }
            }}>
              <Input placeholder={`Ask the tutor about ${s.topic?.name ?? "this topic"}…`} value={ask} onChange={(e) => setAsk(e.target.value)} aria-label="Ask the tutor" />
              <Button type="submit" variant="secondary" loading={askBusy}>Ask</Button>
            </form>
            {asked && (
              <div className="mt-3 space-y-2 rounded-md bg-surface-2 p-3 text-sm">
                <p className="whitespace-pre-wrap">{String(asked.data.explanation).replace(/\[S\d+\]/g, "")}</p>
                <GroundingBar env={asked} />
                {asked.citations.length > 0 && <p className="text-2xs text-muted">Sources: {asked.citations.map((c) => c.title).join(" · ")}</p>}
              </div>
            )}
            <div className="mt-5 flex justify-end"><Button onClick={next("example")}>See a worked example</Button></div>
          </>
        )}

        {step === "example" && (
          <>
            {teachView("worked_example", s.worked_example, "No worked example for this topic yet.")}
            <div className="mt-5 flex justify-end">
              <Button onClick={next(s.followup ? "followup" : s.quiz.length ? "quiz" : "confidence")}>
                {s.followup ? "Try a follow-up" : "Continue"}
              </Button>
            </div>
          </>
        )}

        {step === "followup" && s.followup && (
          <>
            <QuestionBlock label={`Follow-up · ${res(s.question)?.correct ? "stepping up" : "consolidating"}`} q={s.followup}
              result={res(s.followup)} onSubmit={(a, ms) => answer(s.followup!, a, ms)} />
            {res(s.followup) && <div className="mt-4 flex justify-end"><Button onClick={next(s.quiz.length ? "quiz" : "confidence")}>Start mini quiz</Button></div>}
          </>
        )}

        {step === "quiz" && (() => {
          const q = s.quiz[Math.min(quizIdx, s.quiz.length - 1)];
          return (
            <>
              <QuestionBlock label={`Mini quiz · ${Math.min(quizIdx, s.quiz.length - 1) + 1} of ${s.quiz.length}`} q={q}
                result={res(q)} onSubmit={(a, ms) => answer(q, a, ms)} />
              {res(q) && (
                <div className="mt-4 flex justify-end">
                  {quizIdx < s.quiz.length - 1
                    ? <Button onClick={() => setQuizIdx(quizIdx + 1)}>Next question</Button>
                    : quizDone && <Button onClick={next("confidence")}>Confidence check</Button>}
                </div>
              )}
            </>
          );
        })()}

        {step === "confidence" && (
          <div className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">How confident do you feel about {s.topic?.name} now?</h2>
              <p className="mt-1 text-sm text-muted">Your rating is stored next to your measured accuracy — the gap between the two is useful later.</p>
            </div>
            <div className="grid grid-cols-5 gap-2" role="radiogroup" aria-label="Confidence">
              {CONFIDENCE.map((label, i) => (
                <button key={label} role="radio" aria-checked={confidence === i + 1} onClick={() => setConfidence(i + 1)}
                  className={clsx("rounded-md border px-2 py-3 text-center transition-colors",
                    confidence === i + 1 ? "border-accent bg-accent-soft text-accent" : "border-border hover:bg-surface-2")}>
                  <div className="tabular text-lg font-semibold">{i + 1}</div>
                  <div className="text-2xs text-muted">{label}</div>
                </button>
              ))}
            </div>
            <div className="flex justify-end"><Button disabled={!confidence} loading={completing} onClick={complete}>Update my skill graph</Button></div>
          </div>
        )}

        {step === "done" && s.result && (
          <div className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Cycle complete</h2>
              <p className="mt-1 text-sm text-muted">
                Scored <span className="tabular font-medium text-text">{s.result.score} / {s.result.max_score}</span> · self-rated confidence {s.confidence}/5 ({CONFIDENCE[(s.confidence ?? 1) - 1]}).
              </p>
            </div>
            <div className="space-y-3">
              {s.result.changes.map((c) => {
                const d = c.after - c.before;
                return (
                  <div key={c.skill_id} className="rounded-md border border-border p-3">
                    <div className="mb-2 flex items-center justify-between text-sm">
                      <span className="font-medium">{c.skill}</span>
                      <span className={clsx("tabular text-xs font-medium", d >= 0 ? "text-ok" : "text-danger")}>
                        {Math.round(c.before)} → {Math.round(c.after)} ({d >= 0 ? "+" : ""}{d.toFixed(1)})
                      </span>
                    </div>
                    <MasteryBar value={c.after} />
                  </div>
                );
              })}
              {s.result.changes.length === 0 && <Prose text="No scorable answers in this cycle, so mastery was not changed." />}
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <Link href="/skills"><Button variant="secondary">View skill graph</Button></Link>
              <Link href="/study"><Button>Study another topic</Button></Link>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
