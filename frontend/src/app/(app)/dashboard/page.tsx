"use client";

import Link from "next/link";
import { useMemo } from "react";
import { PatternDisclaimer } from "@/components/company";
import { MasteryBar } from "@/components/Mastery";
import { Badge, Button, Card, CardHeader, CompanyTag, EmptyState, ErrorState, Skeleton, Stat } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { fmtDate, pct } from "@/lib/format";
import type { Company, CompanyReadiness, Dashboard, Profile } from "@/lib/types";
import { useApi } from "@/lib/useApi";

const AREA_LABEL: Record<string, string> = {
  DSA: "Data structures & algorithms", DBMS: "Databases", OS: "Operating systems", CN: "Computer networks",
  OOP: "Object-oriented programming", Aptitude: "Aptitude",
};

export default function DashboardPage() {
  const { user } = useAuth();
  const dash = useApi<Dashboard>("/me/dashboard");
  const profile = useApi<Profile>("/users/me/profile");
  const companies = useApi<Company[]>("/companies");
  const readiness = useApi<CompanyReadiness[]>("/me/readiness/companies");

  const targets = useMemo(
    () => (companies.data ?? []).filter((c) => profile.data?.target_company_ids.includes(c.id)),
    [companies.data, profile.data],
  );
  const d = dash.data;
  const p = profile.data;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Welcome back, {user?.full_name.split(" ")[0]}</h1>
          <p className="mt-0.5 text-sm text-muted">Your preparation at a glance.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/tests"><Button variant="secondary">Take a test</Button></Link>
          <Link href="/study"><Button>Continue studying</Button></Link>
        </div>
      </div>

      {(dash.error || profile.error) && <ErrorState message={(dash.error ?? profile.error)!.message} onRetry={() => { dash.reload(); profile.reload(); }} />}

      {p && p.completeness < 100 && (
        <Card className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="tabular grid size-10 place-items-center rounded-full border-2 border-accent text-xs font-semibold text-accent">{p.completeness}%</div>
            <div>
              <p className="text-sm font-medium">Finish your profile</p>
              <p className="text-xs text-muted">Target role and companies drive your roadmap and readiness scores.</p>
            </div>
          </div>
          <Link href="/profile"><Button size="sm" variant="secondary">Complete profile</Button></Link>
        </Card>
      )}

      <Card>
        <div className="grid grid-cols-2 divide-border md:grid-cols-4 md:divide-x">
          {!d ? Array.from({ length: 4 }).map((_, i) => <div key={i} className="space-y-2 px-4 py-3"><Skeleton className="h-3 w-20" /><Skeleton className="h-6 w-12" /></div>) : (
            <>
              <Stat label="Study streak" value={`${d.study_streak}d`} hint={d.last_active_on ? `Last active ${d.last_active_on}` : "Start a cycle to begin"} />
              <Stat label="Questions answered" value={d.questions_answered} hint={`${d.questions_answered_30d} in the last 30 days`} />
              <Stat label="Accuracy" value={pct(d.overall_accuracy)} hint="Scored answers only" />
              <Stat label="Topics completed" value={d.topics_completed} hint="Mastery ≥ 70" />
            </>
          )}
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader title="Mastery by area" description="Attempt-weighted skill-graph rollup. Empty until you practise that area."
            actions={<Link href="/skills" className="text-xs text-accent hover:underline">Skill graph</Link>} />
          <div className="divide-y divide-border">
            {!d ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="px-4 py-3"><Skeleton className="h-3 w-full" /></div>) :
              d.areas.map((a) => (
                <div key={a.area} className="flex items-center gap-4 px-4 py-2.5">
                  <div className="w-44 min-w-0">
                    <div className="truncate text-sm">{AREA_LABEL[a.area] ?? a.area}</div>
                    <div className="text-2xs text-muted">{a.attempts ? `${a.attempts} attempt${a.attempts === 1 ? "" : "s"}` : "Not practised yet"}</div>
                  </div>
                  <MasteryBar value={a.mastery} className="flex-1" />
                </div>
              ))}
          </div>
        </Card>

        <div className="space-y-5 lg:col-span-2">
          <Card>
            <CardHeader title="Weakest topics" description="Mastery below 40, lowest first." />
            <div className="p-4">
              {!d ? <Skeleton className="h-10 w-full" /> : d.weak_topics.length === 0 ? (
                <p className="text-sm text-muted">{d.questions_answered ? "No weak topics right now." : "Answer a few questions to find your weak spots."}</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">{d.weak_topics.map((t) => <Badge key={t} tone="danger">{t}</Badge>)}</div>
              )}
            </div>
          </Card>
          <Card>
            <CardHeader title="Target companies" actions={<Link href="/profile" className="text-xs text-accent hover:underline">Edit</Link>} />
            <div className="p-4">
              {companies.loading || profile.loading ? <Skeleton className="h-10 w-full" /> : targets.length === 0 ? (
                <p className="text-sm text-muted">Pick companies in your profile to get company-aware practice.</p>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-1.5">{targets.map((c) => <Link key={c.id} href={`/companies/${c.slug}`}><CompanyTag name={c.name} /></Link>)}</div>
                  <div className="space-y-2">
                    {targets.map((c) => {
                      const r = readiness.data?.find((x) => x.company_id === c.id);
                      return (
                        <Link key={c.id} href={`/readiness/${c.slug}`} className="flex items-center gap-3 text-sm hover:text-accent">
                          <span className="w-24 truncate">{c.name}</span>
                          <MasteryBar value={r?.overall ?? null} className="flex-1" />
                        </Link>
                      );
                    })}
                    <p className="text-2xs text-muted">Readiness % (Equation 3.1, company weights)</p>
                  </div>
                  <PatternDisclaimer text={targets[0].pattern_disclaimer} compact />
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader title="Recent activity" />
        {!d ? <div className="p-4"><Skeleton className="h-16 w-full" /></div> : d.recent_attempts.length === 0 ? (
          <EmptyState title="Nothing yet" description="Completed study cycles and submitted tests show up here." />
        ) : (
          <div className="divide-y divide-border">
            {d.recent_attempts.map((a) => (
              <Link key={a.id} href={a.mode === "test" ? `/tests/attempt/${a.id}/analysis` : `/study/${a.id}`}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2/60">
                <Badge tone={a.mode === "test" ? "info" : "accent"}>{a.mode === "test" ? "Test" : "Study"}</Badge>
                <span className="min-w-0 flex-1 truncate text-sm">{a.title}</span>
                <span className="tabular text-sm text-text-2">{a.score == null ? "—" : `${a.score} / ${a.max_score}`}</span>
                <span className="hidden w-32 text-right text-xs text-muted sm:block">{fmtDate(a.submitted_at)}</span>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
