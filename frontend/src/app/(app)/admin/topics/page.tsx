"use client";

import { useMemo, useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Select, SkeletonRows, Table, Td, Textarea, Th } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { AREAS, type Topic } from "@/lib/types";
import { useApi } from "@/lib/useApi";

type Draft = { id?: number; name: string; area: string; description: string; parent_id: number | null };

export default function TopicsAdmin() {
  const { data, error, loading, reload } = useApi<Topic[]>("/topics");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const byId = useMemo(() => new Map((data ?? []).map((t) => [t.id, t])), [data]);
  // Order as a tree: parents followed by children
  const ordered = useMemo(() => {
    const list = data ?? [];
    const out: { t: Topic; depth: number }[] = [];
    const walk = (parent: number | null, depth: number) =>
      list.filter((t) => t.parent_id === parent).forEach((t) => { out.push({ t, depth }); walk(t.id, depth + 1); });
    walk(null, 0);
    list.filter((t) => t.parent_id && !byId.has(t.parent_id)).forEach((t) => out.push({ t, depth: 0 }));
    return out;
  }, [data, byId]);

  async function save() {
    if (!draft) return;
    setSaving(true);
    setFormError(null);
    const body = { name: draft.name, area: draft.area, description: draft.description, parent_id: draft.parent_id };
    try {
      await api(draft.id ? `/topics/${draft.id}` : "/topics", { method: draft.id ? "PATCH" : "POST", json: body });
      setDraft(null);
      await reload();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function remove(t: Topic) {
    if (!confirm(`Delete topic “${t.name}”? Questions keep existing but lose this tag.`)) return;
    await api(`/topics/${t.id}`, { method: "DELETE" }).catch(() => undefined);
    await reload();
  }

  return (
    <div>
      <PageHeader title="Topics" description="Hierarchical taxonomy used to tag questions."
        actions={<Button onClick={() => { setFormError(null); setDraft({ name: "", area: "DSA", description: "", parent_id: null }); }}>New topic</Button>} />
      <Card>
        {error ? <div className="p-4"><ErrorState message={error.message} onRetry={reload} /></div> :
          loading && !data ? <SkeletonRows rows={8} cols={3} /> :
            ordered.length === 0 ? <EmptyState title="No topics yet" /> : (
              <Table>
                <thead><tr><Th>Name</Th><Th>Area</Th><Th>Published questions</Th><Th /></tr></thead>
                <tbody>
                  {ordered.map(({ t, depth }) => (
                    <tr key={t.id} className="hover:bg-surface-2/60">
                      <Td><span style={{ paddingLeft: depth * 18 }} className={depth ? "text-text-2" : "font-medium"}>{depth > 0 && <span className="mr-1.5 text-muted">└</span>}{t.name}</span></Td>
                      <Td><Badge>{t.area}</Badge></Td>
                      <Td className="tabular text-text-2">{t.question_count}</Td>
                      <Td className="text-right">
                        <Button size="sm" variant="ghost" onClick={() => { setFormError(null); setDraft({ id: t.id, name: t.name, area: t.area, description: t.description, parent_id: t.parent_id }); }}>Edit</Button>
                        <Button size="sm" variant="ghost" className="text-danger" onClick={() => remove(t)}>Delete</Button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
      </Card>

      <Modal open={!!draft} onClose={() => setDraft(null)} title={draft?.id ? "Edit topic" : "New topic"}
        footer={<><Button variant="secondary" onClick={() => setDraft(null)}>Cancel</Button><Button onClick={save} loading={saving} disabled={!draft?.name.trim()}>Save</Button></>}>
        {draft && (
          <div className="space-y-3">
            {formError && <ErrorState message={formError} />}
            <Field label="Name"><Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Area">
                <Select value={draft.area} onChange={(e) => setDraft({ ...draft, area: e.target.value })}>{AREAS.map((a) => <option key={a}>{a}</option>)}</Select>
              </Field>
              <Field label="Parent topic">
                <Select value={draft.parent_id ?? ""} onChange={(e) => setDraft({ ...draft, parent_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">— none (top level) —</option>
                  {(data ?? []).filter((t) => t.id !== draft.id).map((t) => <option key={t.id} value={t.id}>{t.area} · {t.name}</option>)}
                </Select>
              </Field>
            </div>
            <Field label="Description"><Textarea rows={3} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></Field>
          </div>
        )}
      </Modal>
    </div>
  );
}
