"use client";

import clsx from "clsx";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { type CodeLang, judge, LANG_LABEL, STARTER, type SubmissionView, VERDICT_TONE } from "@/lib/judge";
import { CodeEditor } from "./CodeEditor";
import { CodeReviewPanel } from "./CodeReviewPanel";
import { Badge, Button, Select, Spinner, Textarea } from "./ui";

const CODE_LANGS: CodeLang[] = ["python", "cpp", "java", "javascript"];

function draftKey(qid: number, lang: string) { return `pp-draft:${qid}:${lang}`; }
function loadDraft(qid: number, lang: CodeLang): string {
  try { return localStorage.getItem(draftKey(qid, lang)) ?? STARTER[lang]; } catch { return STARTER[lang]; }
}

function Pre({ label, text, tone }: { label: string; text: string | null | undefined; tone?: "danger" }) {
  return (
    <div className="min-w-0">
      <div className="mb-1 text-2xs font-medium uppercase tracking-wide text-muted">{label}</div>
      <pre className={clsx("max-h-40 overflow-auto rounded-md border border-border bg-surface-2 px-2.5 py-2 font-mono text-xs leading-relaxed",
        tone === "danger" && "text-danger")}>{text === null || text === undefined || text === "" ? <span className="text-muted">(empty)</span> : text}</pre>
    </div>
  );
}

export function ResultPanel({ sub }: { sub: SubmissionView | null }) {
  if (!sub) {
    return <p className="p-4 text-sm text-muted">Run your code on the sample tests, or submit to be judged on the hidden tests. Execution happens in the Judge0 sandbox, never on our servers.</p>;
  }
  const v = sub.verdict!;
  const d = v.details;
  if (!v.done) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-text-2" aria-live="polite">
        <Spinner /> {v.status === "queued" ? "Queued for the sandbox…" : "Running on Judge0…"}
      </div>
    );
  }
  return (
    <div className="space-y-3 p-4" aria-live="polite">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={VERDICT_TONE[v.status] ?? "neutral"} className="h-6 px-2 text-xs">{v.label}</Badge>
        {d.total != null && d.total > 0 && <span className="tabular text-sm text-text-2">{d.passed} / {d.total} tests passed</span>}
        {d.max_time_s != null && <span className="tabular text-xs text-muted">· {d.max_time_s.toFixed(3)} s</span>}
        {d.max_memory_kb != null && <span className="tabular text-xs text-muted">· {(d.max_memory_kb / 1024).toFixed(1)} MB</span>}
        <span className="ml-auto text-2xs text-muted">{sub.mode === "run" ? "Run · sample tests" : "Submit · hidden tests"} · verdict by Judge0</span>
      </div>
      {v.status === "internal_error" && <p className="text-sm text-muted">The sandbox could not be reached ({d.error ?? "unknown error"}). Nothing was scored; try again in a moment.</p>}
      {d.compile_output && <Pre label="Compiler output" text={d.compile_output} tone="danger" />}
      {(d.cases ?? []).filter((c) => c.visible).map((c, i) => (
        <div key={i} className="space-y-2 rounded-md border border-border p-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-medium">{c.expected == null ? "Custom input" : `Sample ${i + 1}`}</span>
            <Badge tone={VERDICT_TONE[c.verdict] ?? "neutral"}>{c.label}</Badge>
            {c.time_s != null && <span className="tabular text-muted">{c.time_s.toFixed(3)} s</span>}
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <Pre label="Input" text={c.stdin} />
            {c.expected != null && <Pre label="Expected" text={c.expected} />}
            <Pre label="Your output" text={c.stdout} />
          </div>
          {c.stderr && <Pre label="stderr" text={c.stderr} tone="danger" />}
        </div>
      ))}
      {sub.mode !== "run" && d.first_failed_case != null && (d.cases ?? [])[d.first_failed_case]?.visible === false && (
        <p className="text-xs text-muted">Failed on hidden test #{d.first_failed_case + 1}. Hidden inputs are not shown.</p>
      )}
    </div>
  );
}

/**
 * Editor + language picker + Run/Submit + output.
 * mode="practice": Run and Submit (submit counts for mastery/readiness).
 * mode="test": Run on samples only; the answer is saved by the test and judged on submission.
 */
export function CodeWorkbench({ questionId, isSql, mode = "practice", value, onChange, onSubmitted, disabled }: {
  questionId: number;
  isSql?: boolean;
  mode?: "practice" | "test";
  value?: { code?: string; language?: string } | null;
  onChange?: (v: { code: string; language: CodeLang }) => void;
  onSubmitted?: (s: SubmissionView) => void;
  disabled?: boolean;
}) {
  const initialLang: CodeLang = isSql ? "sql" : ((value?.language as CodeLang) ?? "python");
  const [lang, setLang] = useState<CodeLang>(initialLang);
  const [code, setCode] = useState<string>(value?.code ?? (mode === "practice" ? loadDraft(questionId, initialLang) : STARTER[initialLang]));
  const [sub, setSub] = useState<SubmissionView | null>(null);
  const [busy, setBusy] = useState<"run" | "submit" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [customOn, setCustomOn] = useState(false);
  const [stdin, setStdin] = useState("");
  const started = useRef(Date.now());
  const cancel = useRef({ cancelled: false });

  useEffect(() => () => { cancel.current.cancelled = true; }, []);

  const update = useCallback((next: string, nextLang = lang) => {
    setCode(next);
    if (mode === "practice") { try { localStorage.setItem(draftKey(questionId, nextLang), next); } catch { /* ignore */ } }
    onChange?.({ code: next, language: nextLang });
  }, [lang, mode, onChange, questionId]);

  function switchLang(l: CodeLang) {
    setLang(l);
    const next = mode === "practice" ? loadDraft(questionId, l) : (code.trim() === STARTER[lang].trim() ? STARTER[l] : code);
    update(next, l);
  }

  async function go(kind: "run" | "submit") {
    setBusy(kind);
    setError(null);
    try {
      const s = await judge({
        question_id: questionId, language: lang, code, mode: kind,
        ...(kind === "run" && customOn && !isSql ? { stdin } : {}),
        ...(kind === "submit" ? { time_taken_ms: Date.now() - started.current } : {}),
      }, setSub, cancel.current);
      if (kind === "submit") onSubmitted?.(s);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not reach the judge");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-surface">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
        {isSql ? <Badge tone="info">{LANG_LABEL.sql}</Badge> : (
          <Select aria-label="Language" className="h-7 w-44 text-xs" value={lang} disabled={disabled} onChange={(e) => switchLang(e.target.value as CodeLang)}>
            {CODE_LANGS.map((l) => <option key={l} value={l}>{LANG_LABEL[l]}</option>)}
          </Select>
        )}
        {!isSql && (
          <label className="flex items-center gap-1.5 text-xs text-text-2">
            <input type="checkbox" className="accent-[var(--accent)]" checked={customOn} onChange={(e) => setCustomOn(e.target.checked)} /> Custom input
          </label>
        )}
        <div className="flex-1" />
        {mode === "practice" && <Button size="sm" variant="ghost" onClick={() => update(STARTER[lang])} disabled={!!busy || disabled}>Reset</Button>}
        <Button size="sm" variant="secondary" loading={busy === "run"} disabled={!!busy || disabled || !code.trim()} onClick={() => go("run")}>Run</Button>
        {mode === "practice" && <Button size="sm" loading={busy === "submit"} disabled={!!busy || disabled || !code.trim()} onClick={() => go("submit")}>Submit</Button>}
      </div>
      <div className="min-h-72 flex-1">
        <CodeEditor language={lang} value={code} onChange={(v) => update(v)} readOnly={disabled} />
      </div>
      {customOn && !isSql && (
        <div className="border-t border-border p-3">
          <Textarea rows={3} className="font-mono text-xs" placeholder="stdin for Run" value={stdin} onChange={(e) => setStdin(e.target.value)} aria-label="Custom input" />
        </div>
      )}
      <div className="max-h-[45%] min-h-24 overflow-y-auto border-t border-border">
        {error && <p className="px-4 pt-3 text-sm text-danger">{error}</p>}
        <ResultPanel sub={sub} />
        {sub && mode === "practice" && <CodeReviewPanel key={sub.id} sub={sub} />}
      </div>
      {mode === "test" && <p className="border-t border-border px-3 py-1.5 text-2xs text-muted">Run checks the sample tests only. Your saved code is judged on hidden tests after you submit the whole test.</p>}
    </div>
  );
}
