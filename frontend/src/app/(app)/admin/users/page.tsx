"use client";

import { useDeferredValue, useState } from "react";
import { RequireScope } from "@/components/Guard";
import { Badge, Button, Card, EmptyState, ErrorState, Input, PageHeader, Select, SkeletonRows, Table, Td, Th } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Page, Role, User } from "@/lib/types";
import { useApi } from "@/lib/useApi";

function UsersInner() {
  const { user: me } = useAuth();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const dq = useDeferredValue(q);
  const { data, error, loading, reload, setData } = useApi<Page<User>>(`/users?page_size=100&q=${encodeURIComponent(dq)}${role ? `&role=${role}` : ""}`);
  const [rowError, setRowError] = useState<string | null>(null);

  async function patch(u: User, body: Partial<{ role: Role; is_active: boolean }>) {
    setRowError(null);
    try {
      const out = await api<User>(`/users/${u.id}`, { method: "PATCH", json: body });
      if (data) setData({ ...data, items: data.items.map((x) => (x.id === u.id ? out : x)) });
    } catch (e) {
      setRowError(e instanceof ApiError ? e.message : "Update failed");
    }
  }

  return (
    <div>
      <PageHeader title="Users" description="Assign roles. Role changes apply immediately — scopes are checked against the database on every request." />
      {rowError && <div className="mb-3"><ErrorState message={rowError} /></div>}
      <Card>
        <div className="flex gap-2 border-b border-border p-3">
          <Input placeholder="Search name or email…" className="w-64" value={q} onChange={(e) => setQ(e.target.value)} />
          <Select className="w-44" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">All roles</option><option value="student">Student</option><option value="content_manager">Content manager</option><option value="admin">Admin</option>
          </Select>
        </div>
        {error ? <div className="p-4"><ErrorState message={error.message} onRetry={reload} /></div> :
          loading && !data ? <SkeletonRows rows={5} cols={4} /> :
            !data?.items.length ? <EmptyState title="No users found" /> : (
              <Table>
                <thead><tr><Th>Name</Th><Th>Email</Th><Th>Sign-in</Th><Th>Role</Th><Th>Status</Th><Th /></tr></thead>
                <tbody>
                  {data.items.map((u) => (
                    <tr key={u.id}>
                      <Td className="font-medium">{u.full_name}{u.id === me?.id && <span className="ml-1.5 text-xs text-muted">(you)</span>}</Td>
                      <Td className="text-text-2">{u.email}</Td>
                      <Td><div className="flex gap-1">{u.has_password && <Badge>Email</Badge>}{u.google_linked && <Badge tone="info">Google</Badge>}</div></Td>
                      <Td>
                        <Select className="h-7 w-40 text-xs" value={u.role} disabled={u.id === me?.id} onChange={(e) => patch(u, { role: e.target.value as Role })}>
                          <option value="student">Student</option><option value="content_manager">Content manager</option><option value="admin">Admin</option>
                        </Select>
                      </Td>
                      <Td>{u.is_active ? <Badge tone="ok">Active</Badge> : <Badge tone="danger">Disabled</Badge>}</Td>
                      <Td className="text-right">
                        {u.id !== me?.id && <Button size="sm" variant="ghost" onClick={() => patch(u, { is_active: !u.is_active })}>{u.is_active ? "Disable" : "Enable"}</Button>}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
      </Card>
    </div>
  );
}

export default function UsersPage() {
  return <RequireScope scope="users:manage"><UsersInner /></RequireScope>;
}
