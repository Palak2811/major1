"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Badge, Button, Card, CardHeader, ErrorState, Field, Input, PageHeader, Select, Skeleton } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { Company, Profile } from "@/lib/types";
import { useApi } from "@/lib/useApi";

function ProfileForm() {
  const params = useSearchParams();
  const profile = useApi<Profile>("/users/me/profile");
  const companies = useApi<Company[]>("/companies");
  const [form, setForm] = useState<Profile | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => { if (profile.data) setForm(profile.data); }, [profile.data]);

  if (profile.error) return <ErrorState message={profile.error.message} onRetry={profile.reload} />;
  if (!form) return <div className="space-y-3"><Skeleton className="h-6 w-40" /><Skeleton className="h-64 w-full" /></div>;

  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setForm({ ...form, [k]: v });
  const toggleCompany = (id: number) =>
    set("target_company_ids", form.target_company_ids.includes(id) ? form.target_company_ids.filter((x) => x !== id) : [...form.target_company_ids, id]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setSaving(true);
    setMsg(null);
    try {
      const out = await api<Profile>("/users/me/profile", {
        method: "PUT",
        json: {
          full_name: form.full_name, college: form.college, branch: form.branch,
          graduation_year: form.graduation_year, target_role: form.target_role,
          target_company_ids: form.target_company_ids, preferred_language: form.preferred_language,
        },
      });
      profile.setData(out);
      setMsg({ ok: true, text: "Profile saved" });
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiError ? err.message : "Save failed" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-5">
      <PageHeader title="Profile" description={params.get("welcome") ? "Welcome! Tell us where you’re headed so we can personalise your prep." : "Your profile anchors every recommendation on the platform."}
        actions={<><span className="text-xs text-muted">{form.completeness}% complete</span><Button type="submit" loading={saving}>Save changes</Button></>} />
      {msg && (msg.ok ? <div className="rounded-md bg-ok-soft px-3 py-2 text-sm text-ok">{msg.text}</div> : <ErrorState message={msg.text} />)}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Academic" />
          <div className="grid gap-3 p-4 sm:grid-cols-2">
            <div className="sm:col-span-2"><Field label="Full name"><Input value={form.full_name} onChange={(e) => set("full_name", e.target.value)} /></Field></div>
            <div className="sm:col-span-2"><Field label="College"><Input value={form.college} onChange={(e) => set("college", e.target.value)} /></Field></div>
            <Field label="Branch"><Input value={form.branch} placeholder="e.g. CSE" onChange={(e) => set("branch", e.target.value)} /></Field>
            <Field label="Graduation year">
              <Input type="number" min={2000} max={2100} value={form.graduation_year ?? ""} onChange={(e) => set("graduation_year", e.target.value ? Number(e.target.value) : null)} />
            </Field>
          </div>
        </Card>

        <Card>
          <CardHeader title="Intent" description="What you are preparing for." />
          <div className="space-y-3 p-4">
            <Field label="Target role"><Input value={form.target_role} placeholder="e.g. Software Development Engineer" onChange={(e) => set("target_role", e.target.value)} /></Field>
            <Field label="Preferred language">
              <Select value={form.preferred_language} onChange={(e) => set("preferred_language", e.target.value as Profile["preferred_language"])}>
                <option value="python">Python</option><option value="cpp">C++</option><option value="java">Java</option><option value="javascript">JavaScript</option>
              </Select>
            </Field>
            <Field label="Target companies" hint="Up to 10.">
              {companies.loading ? <Skeleton className="h-8 w-full" /> : (
                <div className="flex flex-wrap gap-1.5">
                  {(companies.data ?? []).map((c) => {
                    const on = form.target_company_ids.includes(c.id);
                    return (
                      <button type="button" key={c.id} onClick={() => toggleCompany(c.id)} aria-pressed={on}
                        className={`h-7 rounded-md border px-2.5 text-xs font-medium transition-colors ${on ? "border-ochre bg-ochre-soft text-ochre" : "border-border text-text-2 hover:bg-surface-2"}`}>
                        {c.name}
                      </button>
                    );
                  })}
                </div>
              )}
            </Field>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Behaviour & competence" description="Maintained by the platform from your activity — not editable." />
          <dl className="grid grid-cols-2 gap-px bg-border sm:grid-cols-4">
            {[
              ["Study streak", `${form.study_streak} days`],
              ["Topics completed", form.topics_completed],
              ["Weak topics", form.weak_topics.length ? form.weak_topics.join(", ") : "—"],
              ["Resume", form.resume_id ? "Uploaded" : "Not uploaded (Phase 4)"],
              ["DSA", form.dsa_score ?? "Not measured"],
              ["CS fundamentals", form.csf_score ?? "Not measured"],
              ["Coding", form.coding_score ?? "Not measured"],
              ["Aptitude", form.aptitude_score ?? "Not measured"],
            ].map(([k, v]) => (
              <div key={k as string} className="bg-surface px-4 py-3">
                <dt className="text-2xs uppercase tracking-wide text-muted">{k}</dt>
                <dd className="mt-1 text-sm">{typeof v === "string" && v.startsWith("Not") ? <Badge>{v}</Badge> : v}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>
    </form>
  );
}

export default function ProfilePage() {
  return <Suspense><ProfileForm /></Suspense>;
}
