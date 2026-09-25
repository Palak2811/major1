"use client";

import { useState } from "react";
import { PatternDisclaimer, SkillWeightBar } from "@/components/company";
import { Button, Card, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Select, SkeletonRows, Table, Td, Textarea, Th } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { Company, Difficulty, OAPattern, ReadinessWeights, SkillWeights } from "@/lib/types";
import { useApi } from "@/lib/useApi";

type Draft = {
  slug?: string;
  name: string;
  description: string;
  skill_weights: SkillWeights;
  oa_pattern: OAPattern & { topicsText: string };
  customReadiness: boolean;
  readiness_weights: ReadinessWeights;
};

const DEFAULT_READINESS: ReadinessWeights = { dsa: 0.25, csf: 0.2, coding: 0.2, aptitude: 0.15, interview: 0.1, consistency: 0.1 };
const SW_KEYS: [keyof SkillWeights, string][] = [["dsa", "DSA"], ["oop", "OOP"], ["dbms", "DBMS"], ["os", "OS"], ["aptitude", "Aptitude"], ["hr", "HR"]];
const RW_KEYS: [keyof ReadinessWeights, string][] = [["dsa", "DSA"], ["csf", "CS fund."], ["coding", "Coding"], ["aptitude", "Aptitude"], ["interview", "Interview"], ["consistency", "Consistency"]];

const blank = (): Draft => ({
  name: "", description: "",
  skill_weights: { dsa: 40, oop: 10, dbms: 10, os: 10, aptitude: 20, hr: 10 },
  oa_pattern: { coding_questions: 2, mcqs: 20, duration_minutes: 90, difficulty: "medium", frequent_topics: [], topicsText: "" },
  customReadiness: false, readiness_weights: DEFAULT_READINESS,
});

const fromCompany = (c: Company): Draft => ({
  slug: c.slug, name: c.name, description: c.description, skill_weights: c.skill_weights,
  oa_pattern: { ...c.oa_pattern, topicsText: c.oa_pattern.frequent_topics.join(", ") },
  customReadiness: !!c.readiness_weights, readiness_weights: c.readiness_weights ?? DEFAULT_READINESS,
});

export default function CompaniesAdmin() {
  const { data, error, loading, reload } = useApi<Company[]>("/companies");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const swTotal = draft ? SW_KEYS.reduce((s, [k]) => s + (Number(draft.skill_weights[k]) || 0), 0) : 0;
  const rwTotal = draft ? RW_KEYS.reduce((s, [k]) => s + (Number(draft.readiness_weights[k]) || 0), 0) : 0;
  const rwOk = !draft?.customReadiness || Math.abs(rwTotal - 1) < 1e-6;

  async function save() {
    if (!draft) return;
    setSaving(true);
    setFormError(null);
    const { topicsText, ...oa } = draft.oa_pattern;
    const body = {
      name: draft.name, description: draft.description, skill_weights: draft.skill_weights,
      oa_pattern: { ...oa, frequent_topics: topicsText.split(",").map((s) => s.trim()).filter(Boolean) },
      readiness_weights: draft.customReadiness ? draft.readiness_weights : null,
    };
    try {
      await api(draft.slug ? `/companies/${draft.slug}` : "/companies", { method: draft.slug ? "PATCH" : "POST", json: body });
      setDraft(null);
      await reload();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function remove(c: Company) {
    if (!confirm(`Delete ${c.name}? Question tags for this company are removed.`)) return;
    await api(`/companies/${c.slug}`, { method: "DELETE" }).catch(() => undefined);
    await reload();
  }

  const num = (v: string) => (v === "" ? 0 : Number(v));

  return (
    <div>
      <PageHeader title="Company profiles" description="Structured, observed preparation patterns per company."
        actions={<Button onClick={() => { setFormError(null); setDraft(blank()); }}>New company</Button>} />
      <Card>
        {error ? <div className="p-4"><ErrorState message={error.message} onRetry={reload} /></div> :
          loading && !data ? <SkeletonRows rows={4} cols={4} /> :
            !data?.length ? <EmptyState title="No companies yet" /> : (
              <Table>
                <thead><tr><Th>Company</Th><Th>OA pattern</Th><Th className="w-80">Skill weights</Th><Th>Readiness weights</Th><Th /></tr></thead>
                <tbody>
                  {data.map((c) => (
                    <tr key={c.id} className="hover:bg-surface-2/60">
                      <Td className="font-medium">{c.name}</Td>
                      <Td className="tabular text-xs text-text-2">{c.oa_pattern.coding_questions} coding · {c.oa_pattern.mcqs} MCQ · {c.oa_pattern.duration_minutes}m</Td>
                      <Td className="py-2"><SkillWeightBar weights={c.skill_weights} /></Td>
                      <Td className="text-xs text-text-2">{c.readiness_weights ? "Custom" : "Default (Eq. 3.1)"}</Td>
                      <Td className="text-right">
                        <Button size="sm" variant="ghost" onClick={() => { setFormError(null); setDraft(fromCompany(c)); }}>Edit</Button>
                        <Button size="sm" variant="ghost" className="text-danger" onClick={() => remove(c)}>Delete</Button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
      </Card>

      <Modal wide open={!!draft} onClose={() => setDraft(null)} title={draft?.slug ? `Edit ${draft.name}` : "New company"}
        footer={<><Button variant="secondary" onClick={() => setDraft(null)}>Cancel</Button>
          <Button onClick={save} loading={saving} disabled={!draft?.name.trim() || Math.abs(swTotal - 100) > 0.01 || !rwOk}>Save</Button></>}>
        {draft && (
          <div className="space-y-4">
            {formError && <ErrorState message={formError} />}
            <PatternDisclaimer text="Everything entered here is shown to students as an observed historical preparation pattern, not an official specification." />
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Name"><Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></Field>
              <div className="sm:col-span-2"><Field label="Description"><Textarea rows={1} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></Field></div>
            </div>

            <fieldset>
              <legend className="mb-2 text-xs font-semibold text-text-2">Observed OA pattern</legend>
              <div className="grid gap-3 sm:grid-cols-4">
                <Field label="Coding questions"><Input type="number" min={0} value={draft.oa_pattern.coding_questions} onChange={(e) => setDraft({ ...draft, oa_pattern: { ...draft.oa_pattern, coding_questions: num(e.target.value) } })} /></Field>
                <Field label="MCQs"><Input type="number" min={0} value={draft.oa_pattern.mcqs} onChange={(e) => setDraft({ ...draft, oa_pattern: { ...draft.oa_pattern, mcqs: num(e.target.value) } })} /></Field>
                <Field label="Duration (min)"><Input type="number" min={5} value={draft.oa_pattern.duration_minutes} onChange={(e) => setDraft({ ...draft, oa_pattern: { ...draft.oa_pattern, duration_minutes: num(e.target.value) } })} /></Field>
                <Field label="Difficulty">
                  <Select value={draft.oa_pattern.difficulty} onChange={(e) => setDraft({ ...draft, oa_pattern: { ...draft.oa_pattern, difficulty: e.target.value as Difficulty } })}>
                    <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
                  </Select>
                </Field>
              </div>
              <div className="mt-3"><Field label="Frequently tested topics" hint="Comma-separated"><Input value={draft.oa_pattern.topicsText} onChange={(e) => setDraft({ ...draft, oa_pattern: { ...draft.oa_pattern, topicsText: e.target.value } })} /></Field></div>
            </fieldset>

            <fieldset>
              <legend className="mb-2 flex w-full items-center justify-between text-xs font-semibold text-text-2">
                Expected skill-weight distribution (%)
                <span className={`tabular font-normal ${Math.abs(swTotal - 100) > 0.01 ? "text-danger" : "text-ok"}`}>Total {swTotal} / 100</span>
              </legend>
              <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
                {SW_KEYS.map(([k, l]) => (
                  <Field key={k} label={l}><Input type="number" min={0} max={100} value={draft.skill_weights[k]} onChange={(e) => setDraft({ ...draft, skill_weights: { ...draft.skill_weights, [k]: num(e.target.value) } })} /></Field>
                ))}
              </div>
            </fieldset>

            <fieldset>
              <legend className="mb-2 flex w-full items-center justify-between text-xs font-semibold text-text-2">
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={draft.customReadiness} onChange={(e) => setDraft({ ...draft, customReadiness: e.target.checked })} className="accent-[var(--accent)]" />
                  Override readiness weights (Equation 3.1)
                </label>
                {draft.customReadiness && <span className={`tabular font-normal ${rwOk ? "text-ok" : "text-danger"}`}>Total {rwTotal.toFixed(2)} / 1.00</span>}
              </legend>
              {draft.customReadiness && (
                <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
                  {RW_KEYS.map(([k, l]) => (
                    <Field key={k} label={l}><Input type="number" step="0.05" min={0} max={1} value={draft.readiness_weights[k]} onChange={(e) => setDraft({ ...draft, readiness_weights: { ...draft.readiness_weights, [k]: num(e.target.value) } })} /></Field>
                  ))}
                </div>
              )}
            </fieldset>
          </div>
        )}
      </Modal>
    </div>
  );
}
