"use client";

import clsx from "clsx";
import { useRouter } from "next/navigation";
import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnswerInput } from "@/components/AnswerInput";
import { QuestionView } from "@/components/QuestionView";
import { Badge, Button, Card, ErrorState, Modal, Skeleton, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtClock } from "@/lib/format";
import type { Answer, AttemptView, SavedAnswer } from "@/lib/types";
import { TYPE_LABEL } from "@/lib/types";
import { useApi } from "@/lib/useApi";

const SAVE_DEBOUNCE_MS = 700;

export default function AttemptPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data, error, reload } = useApi<AttemptView>(`/attempts/${id}`);

  const [answers, setAnswers] = useState<Record<string, SavedAnswer>>({});
  const [current, setCurrent] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [saving, setSaving] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const offset = useRef(0); // server clock − client clock
  const pendingMs = useRef<Record<number, number>>({});
  const activeSince = useRef(Date.now());
  const timers = useRef<Record<number, ReturnType<typeof setTimeout>>>({});
  const submitted = useRef(false);

  useEffect(() => {
    if (!data) return;
    if (data.status === "submitted") { router.replace(`/tests/attempt/${data.id}/analysis`); return; }
    offset.current = new Date(data.server_now).getTime() - Date.now();
    setAnswers(data.answers);
    setCurrent((c) => c ?? data.items[0]?.tq_id ?? null);
  }, [data, router]);

  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, []);

  const serverNow = now + offset.current;
  const sectionState = useMemo(() => {
    if (!data) return null;
    const deadlines = data.sections.map((s) => ({ name: s.name, end: new Date(s.deadline).getTime() }));
    const active = deadlines.find((s) => s.end > serverNow) ?? null;
    const sequential = new Set(deadlines.map((d) => d.end)).size > 1;
    return { deadlines, active, sequential, final: new Date(data.deadline).getTime() };
  }, [data, serverNow]);

  const accessible = useCallback((section: string) => {
    if (!sectionState) return false;
    if (!sectionState.sequential) return (sectionState.active != null);
    return sectionState.active?.name === section;
  }, [sectionState]);

  /** Move elapsed time on the current question into its pending bucket. */
  const tick = useCallback(() => {
    if (current != null) pendingMs.current[current] = (pendingMs.current[current] ?? 0) + (Date.now() - activeSince.current);
    activeSince.current = Date.now();
  }, [current]);

  const save = useCallback(async (tq: number, patch: { answer?: Answer | null; flagged?: boolean }) => {
    if (tq === current) tick();
    const time_spent_ms = Math.round(pendingMs.current[tq] ?? 0);
    pendingMs.current[tq] = 0;
    setSaving("saving");
    try {
      const out = await api<SavedAnswer & { tq_id: number }>(`/attempts/${id}/answers/${tq}`, { method: "PUT", json: { ...patch, time_spent_ms } });
      setAnswers((a) => ({ ...a, [tq]: { answer: out.answer, time_ms: out.time_ms, flagged: out.flagged } }));
      setSaving("saved");
      setSaveError(null);
    } catch (e) {
      pendingMs.current[tq] = (pendingMs.current[tq] ?? 0) + time_spent_ms;
      setSaving("error");
      setSaveError(e instanceof ApiError ? e.message : "Could not save — check your connection");
    }
  }, [current, id, tick]);

  const submit = useCallback(async () => {
    if (submitted.current) return;
    submitted.current = true;
    setSubmitting(true);
    Object.values(timers.current).forEach(clearTimeout);
    try {
      await api(`/attempts/${id}/submit`, { method: "POST" });
      router.replace(`/tests/attempt/${id}/analysis`);
    } catch (e) {
      submitted.current = false;
      setSubmitting(false);
      setSaveError(e instanceof ApiError ? e.message : "Submit failed");
    }
  }, [id, router]);

  // Auto-submit on expiry; jump to the next section when one ends.
  useEffect(() => {
    if (!data || !sectionState) return;
    if (serverNow >= sectionState.final) { void submit(); return; }
    const cur = data.items.find((i) => i.tq_id === current);
    if (cur && !accessible(cur.section)) {
      const nextItem = data.items.find((i) => accessible(i.section));
      if (nextItem) { tick(); setCurrent(nextItem.tq_id); }
    }
  }, [serverNow, sectionState, data, current, accessible, submit, tick]);

  if (error) return <ErrorState message={error.status === 404 ? "Attempt not found" : error.message} onRetry={reload} />;
  if (!data || !sectionState || current == null) return <div className="space-y-4"><Skeleton className="h-10 w-full" /><Skeleton className="h-80 w-full" /></div>;

  const item = data.items.find((i) => i.tq_id === current)!;
  const idx = data.items.indexOf(item);
  const saved = answers[current];
  const remaining = sectionState.final - serverNow;
  const sectionRemaining = sectionState.active ? sectionState.active.end - serverNow : 0;
  const answeredCount = data.items.filter((i) => answers[i.tq_id]?.answer && Object.keys(answers[i.tq_id].answer!).length).length;
  const flaggedCount = data.items.filter((i) => answers[i.tq_id]?.flagged).length;

  function go(tq: number) { tick(); setCurrent(tq); }

  function onAnswer(a: Answer) {
    setAnswers((prev) => ({ ...prev, [current!]: { ...(prev[current!] ?? { time_ms: 0, flagged: false }), answer: a } }));
    clearTimeout(timers.current[current!]);
    const tq = current!;
    timers.current[tq] = setTimeout(() => void save(tq, { answer: a }), SAVE_DEBOUNCE_MS);
  }

  const visible = data.items.filter((i) => accessible(i.section));
  const vIdx = visible.findIndex((i) => i.tq_id === current);

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <Card className="sticky top-14 z-20 flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2.5">
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">{data.test.title}</div>
          <div className="text-2xs text-muted">
            {sectionState.active ? <>Section <span className="font-medium text-text">{sectionState.active.name}</span>{sectionState.sequential && <> · {fmtClock(sectionRemaining)} left in section</>}</> : "Time is up"}
            {data.test.negative_marking && <> · negative marking on</>}
          </div>
        </div>
        <div className="text-2xs text-muted" aria-live="polite">
          {saving === "saving" ? <span className="inline-flex items-center gap-1"><Spinner className="size-3" /> Saving</span> : saving === "saved" ? "All answers saved" : saving === "error" ? <span className="text-danger">Not saved</span> : ""}
        </div>
        <div className={clsx("tabular rounded-md px-2.5 py-1 font-mono text-base font-semibold",
          remaining < 60_000 ? "bg-danger-soft text-danger" : remaining < 300_000 ? "bg-warn-soft text-warn" : "bg-surface-2")} aria-label="Time remaining">
          {fmtClock(remaining)}
        </div>
        <Button variant="secondary" onClick={() => setConfirm(true)} disabled={submitting}>Submit test</Button>
      </Card>

      {saveError && <ErrorState message={saveError} />}

      <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
        <Card className="p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs text-muted">
              <span className="font-semibold text-text">Q{idx + 1}</span>
              <Badge>{TYPE_LABEL[item.question.type]}</Badge>
              <span className="tabular">+{item.marks}{item.negative_marks ? ` / −${item.negative_marks}` : ""}</span>
            </div>
            <Button size="sm" variant={saved?.flagged ? "secondary" : "ghost"} onClick={() => save(current, { flagged: !saved?.flagged })}
              className={saved?.flagged ? "text-ochre" : undefined} aria-pressed={!!saved?.flagged}>
              {saved?.flagged ? "★ Flagged for review" : "☆ Flag for review"}
            </Button>
          </div>
          <h2 className="mb-3 text-lg font-semibold tracking-tight">{item.question.title}</h2>
          <QuestionView q={item.question} hideOptions hideTags />
          <div className="mt-5">
            <AnswerInput key={current} q={item.question} value={saved?.answer ?? null} onChange={onAnswer} disabled={!accessible(item.section) || submitting} />
          </div>
          <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
            <Button variant="secondary" disabled={vIdx <= 0} onClick={() => go(visible[vIdx - 1].tq_id)}>Previous</Button>
            {saved?.answer && Object.keys(saved.answer).length > 0 &&
              <Button variant="ghost" size="sm" onClick={() => { clearTimeout(timers.current[current]); setAnswers((p) => ({ ...p, [current]: { ...p[current], answer: null } })); void save(current, { answer: {} }); }}>Clear answer</Button>}
            {vIdx < visible.length - 1
              ? <Button onClick={() => go(visible[vIdx + 1].tq_id)}>Next</Button>
              : <Button onClick={() => setConfirm(true)}>Review &amp; submit</Button>}
          </div>
        </Card>

        {/* Navigation panel */}
        <Card className="h-fit p-4 lg:sticky lg:top-32">
          {data.sections.map((sec) => {
            const items = data.items.filter((i) => i.section === sec.name);
            const open = accessible(sec.name);
            const ended = new Date(sec.deadline).getTime() <= serverNow;
            return (
              <div key={sec.name} className="mb-4 last:mb-0">
                <div className="mb-2 flex items-center justify-between text-xs">
                  <span className="font-medium">{sec.name}</span>
                  {!open && <span className="text-muted">{ended ? "Ended" : "Locked"}</span>}
                </div>
                <div className="grid grid-cols-6 gap-1.5">
                  {items.map((i) => {
                    const a = answers[i.tq_id];
                    const done = !!a?.answer && Object.keys(a.answer).length > 0;
                    return (
                      <button key={i.tq_id} disabled={!open} onClick={() => go(i.tq_id)}
                        aria-label={`Question ${data.items.indexOf(i) + 1}${done ? ", answered" : ""}${a?.flagged ? ", flagged" : ""}`}
                        className={clsx("tabular relative h-8 rounded-md border text-xs font-medium transition-colors disabled:opacity-40",
                          i.tq_id === current ? "border-text" : "border-border",
                          done ? "bg-accent text-accent-fg" : "bg-surface hover:bg-surface-2")}>
                        {data.items.indexOf(i) + 1}
                        {a?.flagged && <span className="absolute -right-1 -top-1 size-2.5 rounded-full border-2 border-surface bg-ochre" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
          <div className="mt-4 space-y-1 border-t border-border pt-3 text-2xs text-muted">
            <div className="flex items-center gap-2"><span className="size-2.5 rounded-sm bg-accent" /> Answered ({answeredCount})</div>
            <div className="flex items-center gap-2"><span className="size-2.5 rounded-full bg-ochre" /> Flagged ({flaggedCount})</div>
            <div className="flex items-center gap-2"><span className="size-2.5 rounded-sm border border-border" /> Not answered ({data.items.length - answeredCount})</div>
          </div>
        </Card>
      </div>

      <Modal open={confirm} onClose={() => setConfirm(false)} title="Submit test?"
        footer={<><Button variant="secondary" onClick={() => setConfirm(false)}>Keep working</Button><Button loading={submitting} onClick={submit}>Submit now</Button></>}>
        <div className="space-y-2 text-sm">
          <p>You have answered <strong>{answeredCount}</strong> of {data.items.length} questions.</p>
          {data.items.length - answeredCount > 0 && <p className="text-warn">{data.items.length - answeredCount} unanswered question(s) will score 0.</p>}
          {flaggedCount > 0 && <p className="text-ochre">{flaggedCount} question(s) are flagged for review.</p>}
          <p className="text-muted">You can’t change answers after submitting.</p>
        </div>
      </Modal>
    </div>
  );
}
