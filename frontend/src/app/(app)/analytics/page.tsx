"use client";

import Link from "next/link";
import { useState } from "react";
import { AccuracyLine, GroupedBars, HBar, Legend, TimeBars } from "@/components/charts";
import { MasteryBar } from "@/components/Mastery";
import { Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, Skeleton, Table, Td, Th } from "@/components/ui";
import { pct } from "@/lib/format";
import type { Analytics } from "@/lib/types";
import { useApi } from "@/lib/useApi";

function Panel({ title, description, children, table, empty }: {
  title: string; description?: string; children: React.ReactNode; table?: React.ReactNode; empty?: boolean;
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <Card>
      <CardHeader title={title} description={description}
        actions={table && !empty ? <Button size="sm" variant="ghost" onClick={() => setAsTable(!asTable)}>{asTable ? "Chart" : "Table"}</Button> : undefined} />
      <div className="p-4">{empty ? <EmptyState title="No data yet" description="Practise or take a test to populate this chart." /> : asTable ? table : children}</div>
    </Card>
  );
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const { data, error, reload } = useApi<Analytics>(`/me/analytics?days=${days}`);

  if (error) return <ErrorState message={error.message} onRetry={reload} />;

  return (
    <div className="space-y-5">
      <PageHeader title="Analytics" description="Every number is computed from your stored attempts and Judge0 verdicts."
        actions={
          <div className="flex rounded-md border border-border p-0.5" role="group" aria-label="Time range">
            {[14, 30, 90].map((d) => (
              <button key={d} onClick={() => setDays(d)} aria-pressed={days === d}
                className={`h-7 rounded px-2.5 text-xs ${days === d ? "bg-surface-3 font-medium" : "text-muted hover:text-text"}`}>{d}d</button>
            ))}
          </div>
        } />

      {!data ? (
        <div className="grid gap-5 lg:grid-cols-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-72" />)}</div>
      ) : (
        <>
          <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="Accuracy over time" description={`Daily share of scored answers that were correct · last ${days} days`}
              empty={!data.accuracy_over_time.some((d) => d.answered)}
              table={<Table><thead><tr><Th>Date</Th><Th className="text-right">Answered</Th><Th className="text-right">Accuracy</Th></tr></thead>
                <tbody>{data.accuracy_over_time.filter((d) => d.answered).map((d) => <tr key={d.date}><Td>{d.date}</Td><Td className="tabular text-right">{d.answered}</Td><Td className="tabular text-right">{pct(d.accuracy)}</Td></tr>)}</tbody></Table>}>
              <AccuracyLine data={data.accuracy_over_time} />
            </Panel>

            <Panel title="Company readiness" description="Equation 3.1 per target company (company weights applied)"
              empty={!data.company_readiness.length}
              table={<Table><thead><tr><Th>Company</Th><Th className="text-right">Readiness</Th></tr></thead>
                <tbody>{data.company_readiness.map((c) => <tr key={c.company_id}><Td>{c.name}</Td><Td className="tabular text-right">{c.overall}</Td></tr>)}</tbody></Table>}>
              <HBar data={data.company_readiness} labelKey="name" valueKey="overall" name="Readiness" unit="%" />
              <div className="mt-2 flex flex-wrap gap-2">
                {data.company_readiness.map((c) => <Link key={c.slug} href={`/readiness/${c.slug}`} className="text-xs text-accent hover:underline">{c.name} report →</Link>)}
              </div>
            </Panel>

            <Panel title="Topic mastery distribution" description="Mastery of every topic you have practised"
              empty={!data.topic_mastery.length}
              table={<Table><thead><tr><Th>Topic</Th><Th>Area</Th><Th className="text-right">Mastery</Th><Th className="text-right">Attempts</Th></tr></thead>
                <tbody>{data.topic_mastery.map((t) => <tr key={t.topic}><Td>{t.topic}</Td><Td>{t.area}</Td><Td className="tabular text-right">{t.mastery}</Td><Td className="tabular text-right">{t.attempts}</Td></tr>)}</tbody></Table>}>
              <HBar data={data.topic_mastery} labelKey="topic" valueKey="mastery" name="Mastery" />
            </Panel>

            <Panel title="Difficulty distribution" description="Distinct questions attempted, and how many you got right"
              empty={!data.difficulty_distribution.some((d) => d.attempted)}
              table={<Table><thead><tr><Th>Difficulty</Th><Th className="text-right">Attempted</Th><Th className="text-right">Correct</Th></tr></thead>
                <tbody>{data.difficulty_distribution.map((d) => <tr key={d.difficulty}><Td className="capitalize">{d.difficulty}</Td><Td className="tabular text-right">{d.attempted}</Td><Td className="tabular text-right">{d.correct}</Td></tr>)}</tbody></Table>}>
              <Legend items={[{ label: "Attempted", color: "var(--chart-1)" }, { label: "Correct", color: "var(--chart-2)" }]} />
              <GroupedBars data={data.difficulty_distribution} labelKey="difficulty"
                series={[{ key: "attempted", name: "Attempted", color: "var(--chart-1)" }, { key: "correct", name: "Correct", color: "var(--chart-2)" }]} />
            </Panel>
          </div>

          <Panel title="Time taken per question" description="Your latest 25 timed answers, in order"
            empty={!data.time_per_question.length}
            table={<Table><thead><tr><Th>Question</Th><Th>Difficulty</Th><Th className="text-right">Time</Th><Th className="text-right">Expected</Th><Th>Result</Th></tr></thead>
              <tbody>{data.time_per_question.map((t) => <tr key={t.submission_id}><Td>{t.title}</Td><Td className="capitalize">{t.difficulty}</Td><Td className="tabular text-right">{Math.round(t.time_ms / 1000)}s</Td><Td className="tabular text-right">{Math.round(t.expected_ms / 1000)}s</Td><Td>{t.correct ? "Correct" : "Incorrect"}</Td></tr>)}</tbody></Table>}>
            <Legend items={[{ label: "Correct", color: "var(--chart-1)" }, { label: "Incorrect", color: "var(--chart-2)" }]} />
            <TimeBars data={data.time_per_question.map((t) => ({ label: t.title, seconds: Math.round(t.time_ms / 1000), expected: Math.round(t.expected_ms / 1000), correct: t.correct }))} />
          </Panel>

          <Card>
            <CardHeader title="Weakest topics" description="Ranked by mastery, lowest first. Confidence is your self-rating; a gap with accuracy suggests over- or under-confidence." />
            {!data.weakest_topics.length ? <EmptyState title="No practised topics yet" /> : (
              <Table>
                <thead><tr><Th className="w-8">#</Th><Th>Topic</Th><Th className="w-56">Mastery</Th><Th className="text-right">Accuracy</Th><Th className="text-right">Confidence</Th><Th className="text-right">Attempts</Th><Th /></tr></thead>
                <tbody>
                  {data.weakest_topics.map((t, i) => (
                    <tr key={t.topic}>
                      <Td className="tabular text-muted">{i + 1}</Td>
                      <Td><div className="font-medium">{t.topic}</div><div className="text-2xs text-muted">{t.area}</div></Td>
                      <Td><MasteryBar value={t.mastery} /></Td>
                      <Td className="tabular text-right">{pct(t.accuracy)}</Td>
                      <Td className="tabular text-right">{pct(t.confidence)}</Td>
                      <Td className="tabular text-right">{t.attempts}</Td>
                      <Td className="text-right"><Link href="/study"><Button size="sm" variant="ghost">Study</Button></Link></Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
