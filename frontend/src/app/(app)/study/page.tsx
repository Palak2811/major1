"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { MasteryBar } from "@/components/Mastery";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, Skeleton, DifficultyBadge } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { SkillNode, StudySession, Topic } from "@/lib/types";
import { useApi } from "@/lib/useApi";

const AREA_ORDER = ["DSA", "DBMS", "OS", "CN", "OOP", "Aptitude", "HR", "General"];

export default function StudyPicker() {
  const router = useRouter();
  const topics = useApi<Topic[]>("/topics");
  const skills = useApi<SkillNode[]>("/me/skills");
  const [starting, setStarting] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const byTopic = useMemo(() => new Map((skills.data ?? []).filter((s) => s.topic_id).map((s) => [s.topic_id!, s])), [skills.data]);

  const groups = useMemo(() => {
    const list = topics.data ?? [];
    const kids = new Map<number | null, Topic[]>();
    list.forEach((t) => kids.set(t.parent_id, [...(kids.get(t.parent_id) ?? []), t]));
    const subtreeCount = (t: Topic): number => t.question_count + (kids.get(t.id) ?? []).reduce((s, c) => s + subtreeCount(c), 0);
    return AREA_ORDER.map((area) => ({
      area,
      parents: (kids.get(null) ?? []).filter((t) => t.area === area).map((p) => ({
        t: p, count: subtreeCount(p),
        children: (kids.get(p.id) ?? []).map((c) => ({ t: c, count: subtreeCount(c) })),
      })),
    })).filter((g) => g.parents.length);
  }, [topics.data]);

  async function start(topicId: number) {
    setStarting(topicId);
    setError(null);
    try {
      const s = await api<StudySession>("/study/sessions", { method: "POST", json: { topic_id: topicId } });
      router.push(`/study/${s.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start a session");
      setStarting(null);
    }
  }

  const loading = topics.loading || skills.loading;

  function Row({ t, count, child }: { t: Topic; count: number; child?: boolean }) {
    const s = byTopic.get(t.id);
    const m = child ? s?.mastery_score : s?.rollup;
    return (
      <div className={`flex items-center gap-4 px-4 py-2.5 ${child ? "pl-9" : ""}`}>
        <div className="min-w-0 flex-1">
          <div className={child ? "text-sm text-text-2" : "text-sm font-medium"}>{t.name}</div>
          <div className="text-2xs text-muted">{count} practice question{count === 1 ? "" : "s"}{s?.attempt_count ? ` · ${s.attempt_count} attempts` : ""}</div>
        </div>
        <MasteryBar value={m} className="hidden w-40 sm:flex" />
        <div className="hidden w-20 md:block">{s && <DifficultyBadge level={s.next_difficulty} />}</div>
        <Button size="sm" variant={child ? "ghost" : "secondary"} disabled={count === 0} loading={starting === t.id} onClick={() => start(t.id)}>
          {count === 0 ? "No questions" : "Study"}
        </Button>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Study mode"
        description="Each cycle: question → explanation → worked example → follow-up → mini quiz → confidence check. Difficulty adapts to your mastery." />
      {error && <div className="mb-4"><ErrorState message={error} /></div>}
      {(topics.error || skills.error) && <ErrorState message={(topics.error ?? skills.error)!.message} onRetry={() => { topics.reload(); skills.reload(); }} />}
      <div className="space-y-4">
        {loading && Array.from({ length: 2 }).map((_, i) => <Card key={i} className="space-y-3 p-4"><Skeleton className="h-4 w-24" /><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /></Card>)}
        {!loading && groups.length === 0 && <Card><EmptyState title="No topics yet" /></Card>}
        {!loading && groups.map((g) => (
          <Card key={g.area}>
            <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
              <h2 className="text-sm font-semibold">{g.area}</h2>
              <Badge>Mastery · next difficulty</Badge>
            </div>
            <div className="divide-y divide-border">
              {g.parents.map((p) => (
                <div key={p.t.id}>
                  <Row t={p.t} count={p.count} />
                  {p.children.map((c) => <Row key={c.t.id} t={c.t} count={c.count} child />)}
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
