"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { Logo } from "./Logo";

type NavItem = { href: string; label: string; icon: React.ReactNode; scope?: string; soon?: string };

const I = (d: string) => (
  <svg viewBox="0 0 16 16" className="size-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d={d} />
  </svg>
);

const LEARN: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: I("M2.5 2.5h4.5v5h-4.5zM9 2.5h4.5v3H9zM9 7.5h4.5v6H9zM2.5 9.5h4.5v4h-4.5z") },
  { href: "/questions", label: "Question bank", icon: I("M3 3.5h10M3 8h10M3 12.5h6") },
  { href: "/companies", label: "Companies", icon: I("M3 13.5V3.5h6.5v10M9.5 6.5H13v7M5 6h2M5 8.5h2M5 11h2") },
  { href: "/readiness", label: "Readiness", icon: I("M8 13.5a5.5 5.5 0 1 1 5.5-5.5M8 8l3-3") },
  { href: "/career", label: "Resume & job fit", icon: I("M3 4.5h10v8H3zM6 4.5V3h4v1.5M3 8h10") },
  { href: "/analytics", label: "Analytics", icon: I("M2.5 13.5h11M4.5 11V8M7.5 11V5M10.5 11V7") },
  { href: "/tutor", label: "AI tutor", icon: I("M8 2.5 9.3 6l3.7.4-2.8 2.4.8 3.7L8 10.6 5 12.5l.8-3.7L3 6.4 6.7 6z") },
  { href: "/study", label: "Study mode", icon: I("M2.5 4 8 2l5.5 2L8 6zM4.5 5v4c0 1 1.6 2 3.5 2s3.5-1 3.5-2V5") },
  { href: "/practice", label: "Coding practice", icon: I("M5.5 5 2.5 8l3 3M10.5 5l3 3-3 3M9 3.5 7 12.5") },
  { href: "/tests", label: "Tests", icon: I("M5 2.5h6M4 4.5h8v9H4zM6 8l1.5 1.5L10 7") },
  { href: "/skills", label: "Skill graph", icon: I("M8 3.5v3M8 6.5 4 10M8 6.5l4 3.5M3 11.5a1 1 0 1 0 2 0 1 1 0 0 0-2 0zM11 11.5a1 1 0 1 0 2 0 1 1 0 0 0-2 0zM7 2.5a1 1 0 1 0 2 0 1 1 0 0 0-2 0z") },
];

const MANAGE: NavItem[] = [
  { href: "/admin", label: "Overview", icon: I("M2.5 13.5h11M4 11V7M7 11V4M10 11V8M13 11V5.5"), scope: "admin:panel" },
  { href: "/admin/questions", label: "Questions", icon: I("M3 3.5h10M3 8h10M3 12.5h6"), scope: "content:write" },
  { href: "/admin/topics", label: "Topics", icon: I("M3 4h4M3 8h7M3 12h5M11 3.5l2 2-2 2"), scope: "content:write" },
  { href: "/admin/tests", label: "Tests", icon: I("M5 2.5h6M4 4.5h8v9H4zM6 8l1.5 1.5L10 7"), scope: "content:write" },
  { href: "/admin/review", label: "AI review queue", icon: I("M3 8.5l3 3 7-7"), scope: "content:write" },
  { href: "/admin/knowledge", label: "Knowledge base", icon: I("M3 3.5h4a1.5 1.5 0 0 1 1.5 1.5v8A1.5 1.5 0 0 0 7 11.5H3zM13 3.5H9.5A1.5 1.5 0 0 0 8 5v8a1.5 1.5 0 0 1 1.5-1.5H13z"), scope: "content:write" },
  { href: "/admin/ai", label: "AI usage", icon: I("M2.5 13.5h11M4 11V7M7 11V4M10 11V8M13 11V5.5"), scope: "admin:panel" },
  { href: "/admin/companies", label: "Companies", icon: I("M3 13.5V3.5h6.5v10M9.5 6.5H13v7"), scope: "content:write" },
  { href: "/admin/users", label: "Users", icon: I("M6 7a2.25 2.25 0 1 0 0-4.5A2.25 2.25 0 0 0 6 7zM2 13.5c0-2.2 1.8-4 4-4s4 1.8 4 4M11 3a2 2 0 0 1 0 4M12.5 9.7c.9.6 1.5 1.6 1.5 2.8"), scope: "users:manage" },
];

const ROLE_LABEL = { student: "Student", content_manager: "Content manager", admin: "Admin" } as const;

function NavLink({ item, active, onNavigate }: { item: NavItem; active: boolean; onNavigate: () => void }) {
  if (item.soon) {
    return (
      <span className="flex h-8 cursor-not-allowed items-center gap-2.5 rounded-md px-2.5 text-sm text-muted/70" title={`Available in ${item.soon}`}>
        {item.icon}<span className="flex-1">{item.label}</span>
        <span className="text-2xs">{item.soon}</span>
      </span>
    );
  }
  return (
    <Link href={item.href} onClick={onNavigate}
      className={clsx("flex h-8 items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors",
        active ? "bg-surface-3 font-medium text-text" : "text-text-2 hover:bg-surface-2 hover:text-text")}>
      <span className={active ? "text-accent" : undefined}>{item.icon}</span>
      {item.label}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout, can } = useAuth();
  const { theme, toggle } = useTheme();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) => href === "/admin" ? pathname === "/admin" : pathname === href || pathname.startsWith(href + "/");
  const manage = MANAGE.filter((i) => !i.scope || can(i.scope));

  const sidebar = (
    <nav className="flex h-full flex-col gap-6 px-3 py-4">
      <div className="px-2.5"><Logo /></div>
      <div className="space-y-0.5">
        <div className="px-2.5 pb-1 text-2xs font-semibold uppercase tracking-wider text-muted">Learn</div>
        {LEARN.map((i) => <NavLink key={i.label} item={i} active={isActive(i.href)} onNavigate={() => setOpen(false)} />)}
      </div>
      {manage.length > 0 && (
        <div className="space-y-0.5">
          <div className="px-2.5 pb-1 text-2xs font-semibold uppercase tracking-wider text-muted">Manage</div>
          {manage.map((i) => <NavLink key={i.label} item={i} active={isActive(i.href)} onNavigate={() => setOpen(false)} />)}
        </div>
      )}
      <div className="mt-auto space-y-0.5">
        <NavLink item={{ href: "/profile", label: "Profile", icon: I("M8 8a2.75 2.75 0 1 0 0-5.5A2.75 2.75 0 0 0 8 8zM3 13.5c0-2.5 2.2-4 5-4s5 1.5 5 4") }} active={isActive("/profile")} onNavigate={() => setOpen(false)} />
      </div>
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 border-r border-border bg-surface md:block">{sidebar}</aside>

      {open && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-border bg-surface" onClick={(e) => e.stopPropagation()}>{sidebar}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-12 items-center gap-3 border-b border-border bg-bg/90 px-4 backdrop-blur">
          <button className="rounded p-1 text-text-2 hover:bg-surface-2 md:hidden" onClick={() => setOpen(true)} aria-label="Open navigation">
            {I("M2.5 4h11M2.5 8h11M2.5 12h11")}
          </button>
          <div className="flex-1" />
          <button onClick={toggle} className="grid size-8 place-items-center rounded-md text-text-2 hover:bg-surface-2" aria-label="Toggle dark mode" title="Toggle theme">
            {theme === "dark"
              ? I("M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6z")
              : I("M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7z")}
          </button>
          {user && (
            <div className="flex items-center gap-2.5 border-l border-border pl-3">
              <div className="grid size-7 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
                {user.full_name.slice(0, 1).toUpperCase() || "?"}
              </div>
              <div className="hidden leading-tight sm:block">
                <div className="text-sm font-medium">{user.full_name}</div>
                <div className="text-2xs text-muted">{ROLE_LABEL[user.role]}</div>
              </div>
              <button onClick={async () => { await logout(); router.replace("/login"); }}
                className="ml-1 rounded-md px-2 py-1 text-xs text-text-2 hover:bg-surface-2 hover:text-text">
                Sign out
              </button>
            </div>
          )}
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}
