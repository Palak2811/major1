"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { MasteryBar } from "@/components/Mastery";
import { Badge, Button, Card, CardHeader, ErrorState, Field, Input, PageHeader, Select, Skeleton, Spinner, Textarea } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { GapReport, JDView, ResumeView } from "@/lib/types";
import { useApi } from "@/lib/useApi";

async function upload(file: File): Promise<ResumeView> {
  const fd = new FormData();
  fd.append("file", file);
  return api<ResumeView>("/career/resume", { method: "POST", body: fd }); // multipart
}

function Chips({ items, tone }: { items?: string[]; tone?: "ok" | "danger" | "neutral" }) {
  if (!items?.length) return <span className="text-xs text-muted">—</span>;
  return <div className="flex flex-wrap gap-1.5">{items.map((s) => <Badge key={s} tone={tone ?? "neutral"}>{s}</Badge>)}</div>;
}

export default function CareerPage() {
  const resumes = useApi<ResumeView[]>("/career/resume");
  const jds = useApi<JDView[]>("/career/jd");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jd, setJd] = useState({ title: "", company_name: "", raw_text: "" });
  const [savingJd, setSavingJd] = useState(false);
  const [sel, setSel] = useState<{ resume?: number; jd?: number }>({});
  const [gap, setGap] = useState<GapReport | null>(null);
  const [gapErr, setGapErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const pending = (resumes.data ?? []).some((r) => r.status === "pending") || (jds.data ?? []).some((j) => j.status === "pending");
  // Parsing is async (background job): poll while anything is pending.
  const reloadResumes = resumes.reload, reloadJds = jds.reload;
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => { reloadResumes(); reloadJds(); }, 2500);
    return () => clearInterval(t);
  }, [pending, reloadResumes, reloadJds]);

  const latest = resumes.data?.[0];
  const resumeId = sel.resume ?? resumes.data?.find((r) => r.status === "parsed")?.id;
  const jdId = sel.jd ?? jds.data?.find((j) => j.status === "parsed")?.id;

  useEffect(() => {
    if (!resumeId || !jdId) return;
    setGapErr(null);
    api<GapReport>(`/career/gap?resume_id=${resumeId}&jd_id=${jdId}`).then(setGap)
      .catch((e) => { setGap(null); setGapErr(e instanceof ApiError ? e.message : "Could not compare"); });
  }, [resumeId, jdId]);

  async function onFile(f: File | undefined) {
    if (!f) return;
    setUploading(true); setError(null);
    try { await upload(f); await resumes.reload(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Upload failed"); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  async function saveJd(e: React.FormEvent) {
    e.preventDefault();
    setSavingJd(true); setError(null);
    try { const j = await api<JDView>("/career/jd", { method: "POST", json: jd }); setSel((s) => ({ ...s, jd: j.id })); setJd({ title: "", company_name: "", raw_text: "" }); await jds.reload(); }
    catch (err) { setError(err instanceof ApiError ? err.message : "Could not save"); }
    finally { setSavingJd(false); }
  }

  const p = latest?.parsed;

  return (
    <div className="space-y-5">
      <PageHeader title="Resume & job fit" description="AI extracts your resume and a job description into structured fields. The job-readiness % and missing-skills list are computed deterministically from those fields." />
      {error && <ErrorState message={error} />}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Resume" description="PDF or TXT, up to 5 MB. Stored privately; only you can see it." actions={
            <>
              <input ref={fileRef} type="file" accept=".pdf,.txt,application/pdf,text/plain" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} />
              <Button size="sm" loading={uploading} onClick={() => fileRef.current?.click()}>{latest ? "Upload new" : "Upload resume"}</Button>
            </>} />
          <div className="space-y-3 p-4">
            {resumes.loading && !resumes.data ? <Skeleton className="h-24 w-full" /> : !latest ? (
              <p className="text-sm text-muted">No resume yet.</p>
            ) : latest.status === "pending" ? (
              <p className="flex items-center gap-2 text-sm text-text-2"><Spinner /> Parsing {latest.filename}…</p>
            ) : latest.status === "failed" ? (
              <ErrorState message={`Couldn't parse ${latest.filename}: ${p?.error}`} />
            ) : (
              <>
                <div className="flex items-center gap-2 text-xs text-muted">{latest.filename} · {fmtDate(latest.created_at)} {p?._mock && <Badge tone="info">Mock AI</Badge>}</div>
                <Field label="Skills"><Chips items={p?.skills} /></Field>
                {!!p?.projects?.length && <Field label="Projects"><ul className="space-y-1 text-sm">{p.projects.map((x) => <li key={x.name}><span className="font-medium">{x.name}</span> <span className="text-xs text-muted">{x.technologies.join(", ")}</span></li>)}</ul></Field>}
                {!!p?.experience?.length && <Field label="Experience"><ul className="space-y-1 text-sm">{p.experience.map((x, i) => <li key={i}>{x.role} · {x.organization} <span className="text-xs text-muted">{x.duration}</span></li>)}</ul></Field>}
                {!!p?.education?.length && <Field label="Education"><ul className="text-sm">{p.education.map((x, i) => <li key={i}>{x.degree}, {x.institution} {x.year}</li>)}</ul></Field>}
                {!!p?.achievements?.length && <Field label="Achievements"><ul className="list-disc pl-4 text-sm">{p.achievements.map((x, i) => <li key={i}>{x}</li>)}</ul></Field>}
              </>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Job description" description="Paste the full posting." />
          <form onSubmit={saveJd} className="space-y-3 p-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Role"><Input required value={jd.title} onChange={(e) => setJd({ ...jd, title: e.target.value })} placeholder="SDE Intern" /></Field>
              <Field label="Company"><Input value={jd.company_name} onChange={(e) => setJd({ ...jd, company_name: e.target.value })} /></Field>
            </div>
            <Field label="Description" hint="At least 50 characters"><Textarea rows={6} required minLength={50} value={jd.raw_text} onChange={(e) => setJd({ ...jd, raw_text: e.target.value })} /></Field>
            <Button type="submit" loading={savingJd}>Analyse job description</Button>
          </form>
        </Card>
      </div>

      <Card>
        <CardHeader title="Skill gap" description="Required skills count double; technologies count once. Aliases (JS → JavaScript, Postgres → PostgreSQL…) are normalised."
          actions={
            <div className="flex gap-2">
              <Select aria-label="Resume" className="h-7 w-44 text-xs" value={resumeId ?? ""} onChange={(e) => setSel({ ...sel, resume: Number(e.target.value) })}>
                {(resumes.data ?? []).filter((r) => r.status === "parsed").map((r) => <option key={r.id} value={r.id}>{r.filename}</option>)}
              </Select>
              <Select aria-label="Job description" className="h-7 w-44 text-xs" value={jdId ?? ""} onChange={(e) => setSel({ ...sel, jd: Number(e.target.value) })}>
                {(jds.data ?? []).map((j) => <option key={j.id} value={j.id} disabled={j.status !== "parsed"}>{j.title}{j.status === "pending" ? " (parsing…)" : ""}</option>)}
              </Select>
            </div>
          } />
        <div className="p-4">
          {!resumeId || !jdId ? <p className="text-sm text-muted">Upload a resume and add a job description to see your fit.</p> :
            gapErr ? <ErrorState message={gapErr} /> : !gap ? <Skeleton className="h-24 w-full" /> : (
              <div className="grid gap-5 lg:grid-cols-[240px_1fr]">
                <div>
                  <div className="text-2xs font-semibold uppercase tracking-wide text-muted">Job readiness</div>
                  <div className="tabular text-5xl font-semibold">{gap.job_readiness}<span className="text-2xl text-muted">%</span></div>
                  <MasteryBar value={gap.job_readiness} showValue={false} className="mt-2" />
                  <p className="mt-2 text-xs text-muted">{gap.matched.length} of {gap.requirements.length} requirements evidenced for “{gap.jd_title}”.</p>
                </div>
                <div className="space-y-4">
                  <Field label="Matched"><Chips items={gap.matched} tone="ok" /></Field>
                  <div>
                    <div className="mb-1.5 text-xs font-medium text-text-2">Missing competencies</div>
                    {gap.missing.length === 0 ? <p className="text-sm text-ok">Nothing missing — great fit.</p> : (
                      <ul className="divide-y divide-border rounded-md border border-border">
                        {gap.missing.map((m) => (
                          <li key={m.skill} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
                            <Badge tone="danger">{m.skill}</Badge>
                            {m.weight === 2 && <Badge>required</Badge>}
                            <span className="flex-1 text-text-2">{m.suggestion}</span>
                            {m.action === "study" && <Link href="/study"><Button size="sm" variant="ghost">Study {m.topic}</Button></Link>}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            )}
        </div>
      </Card>
    </div>
  );
}
