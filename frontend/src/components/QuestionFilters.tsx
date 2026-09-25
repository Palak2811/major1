"use client";

import { useMemo } from "react";
import type { Company, Topic } from "@/lib/types";
import { QUESTION_TYPES, TYPE_LABEL } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { Input, Select } from "./ui";

export function QuestionFilters({ value, onChange, withStatus }: {
  value: Record<string, string>; onChange: (v: Record<string, string>) => void; withStatus?: boolean;
}) {
  const topics = useApi<Topic[]>("/topics");
  const companies = useApi<Company[]>("/companies");
  const set = (k: string, v: string) => onChange({ ...value, [k]: v });
  return (
    <div className="flex flex-wrap gap-2 border-b border-border p-3">
      <Input placeholder="Search title or statement…" className="w-56" value={value.q ?? ""} onChange={(e) => set("q", e.target.value)} />
      <Select className="w-36" value={value.type ?? ""} onChange={(e) => set("type", e.target.value)}>
        <option value="">All types</option>
        {QUESTION_TYPES.map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
      </Select>
      <Select className="w-32" value={value.difficulty ?? ""} onChange={(e) => set("difficulty", e.target.value)}>
        <option value="">Any difficulty</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
      </Select>
      <Select className="w-44" value={value.topic_id ?? ""} onChange={(e) => set("topic_id", e.target.value)}>
        <option value="">All topics</option>
        {(topics.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.area} · {t.name}</option>)}
      </Select>
      <Select className="w-36" value={value.company_id ?? ""} onChange={(e) => set("company_id", e.target.value)}>
        <option value="">All companies</option>
        {(companies.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </Select>
      {withStatus && (
        <Select className="w-32" value={value.status ?? ""} onChange={(e) => set("status", e.target.value)}>
          <option value="">Any status</option><option value="published">Published</option><option value="draft">Draft</option><option value="archived">Archived</option>
        </Select>
      )}
    </div>
  );
}

export function useFilterString(f: Record<string, string>) {
  return useMemo(() => {
    const p = new URLSearchParams();
    Object.entries(f).forEach(([k, v]) => v && p.set(k, v.trim()));
    return p.toString();
  }, [f]);
}
