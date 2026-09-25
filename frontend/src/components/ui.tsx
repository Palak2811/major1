"use client";

import clsx from "clsx";
import { cloneElement, forwardRef, isValidElement, useEffect, useId, useRef } from "react";

/* ---------------- Button ---------------- */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

export const Button = forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize; loading?: boolean }
>(function Button({ variant = "primary", size = "md", loading, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors select-none",
        "disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap",
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-sm",
        variant === "primary" && "bg-accent text-accent-fg hover:bg-accent-hover",
        variant === "secondary" && "border border-border bg-surface text-text hover:bg-surface-2",
        variant === "ghost" && "text-text-2 hover:bg-surface-2 hover:text-text",
        variant === "danger" && "bg-danger text-white hover:opacity-90",
        className,
      )}
      {...rest}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
});

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={clsx("size-3.5 animate-spin", className)} viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeOpacity=".25" strokeWidth="2" />
      <path d="M14 8a6 6 0 0 0-6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/* ---------------- Card ---------------- */

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={clsx("rounded-lg border border-border bg-surface shadow-card", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, description, actions }: { title: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-text">{title}</h3>
        {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ---------------- Form fields ---------------- */

// Width defaults to full unless the caller passes its own w-* class.
const width = (cls?: string) => (cls && /(^|\s)w-/.test(cls) ? "" : "w-full");

const fieldBase =
  "rounded-md border border-border bg-surface px-2.5 text-sm text-text placeholder:text-muted " +
  "hover:border-border-strong focus:border-accent focus:outline-none focus:ring-2 focus:ring-[var(--ring)] " +
  "disabled:opacity-60";

export function Field({ label, hint, error, children, htmlFor }: {
  label: string; hint?: string; error?: string; children: React.ReactNode; htmlFor?: string;
}) {
  // Auto-associate the label with a single form control child.
  const autoId = useId();
  const single = !htmlFor && isValidElement<{ id?: string }>(children) && typeof children.type !== "string"
    ? children : null;
  const id = htmlFor ?? (single ? single.props.id ?? autoId : undefined);
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-xs font-medium text-text-2">{label}</label>
      {single ? cloneElement(single, { id }) : children}
      {error ? <p className="text-xs text-danger">{error}</p> : hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return <input ref={ref} className={clsx(fieldBase, width(className), "h-8", className)} {...rest} />;
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return <textarea ref={ref} className={clsx(fieldBase, width(className), "py-1.5 leading-relaxed", className)} {...rest} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select ref={ref} className={clsx(fieldBase, width(className), "h-8 pr-7", className)} {...rest}>
        {children}
      </select>
    );
  },
);

/* ---------------- Badge ---------------- */

type Tone = "neutral" | "accent" | "ochre" | "ok" | "warn" | "danger" | "info";
const toneCls: Record<Tone, string> = {
  neutral: "bg-surface-2 text-text-2 border-border",
  accent: "bg-accent-soft text-accent border-transparent",
  ochre: "bg-ochre-soft text-ochre border-transparent",
  ok: "bg-ok-soft text-ok border-transparent",
  warn: "bg-warn-soft text-warn border-transparent",
  danger: "bg-danger-soft text-danger border-transparent",
  info: "bg-info-soft text-info border-transparent",
};

export function Badge({ tone = "neutral", children, className, title }: { tone?: Tone; children: React.ReactNode; className?: string; title?: string }) {
  return (
    <span title={title} className={clsx("inline-flex h-5 items-center gap-1 rounded-sm border px-1.5 text-2xs font-medium whitespace-nowrap", toneCls[tone], className)}>
      {children}
    </span>
  );
}

export function CompanyTag({ name }: { name: string }) {
  return (
    <Badge tone="ochre">
      <svg viewBox="0 0 12 12" className="size-2.5" aria-hidden><rect x="2" y="1.5" width="8" height="9" rx="1" fill="none" stroke="currentColor" strokeWidth="1.3" /><path d="M4.5 4h1M6.5 4h1M4.5 6h1M6.5 6h1" stroke="currentColor" strokeWidth="1.2" /></svg>
      {name}
    </Badge>
  );
}

export function TopicTag({ name }: { name: string }) {
  return <Badge tone="accent"># {name}</Badge>;
}

export function DifficultyBadge({ level }: { level: "easy" | "medium" | "hard" }) {
  const tone: Tone = level === "easy" ? "ok" : level === "medium" ? "warn" : "danger";
  return <Badge tone={tone} className="capitalize">{level}</Badge>;
}

/* ---------------- Table ---------------- */

export function Table({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx("overflow-x-auto", className)}>
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}
export function Th({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <th className={clsx("h-8 border-b border-border px-3 text-left text-2xs font-semibold uppercase tracking-wide text-muted", className)}>{children}</th>;
}
export function Td({ children, className, colSpan }: { children?: React.ReactNode; className?: string; colSpan?: number }) {
  return <td colSpan={colSpan} className={clsx("h-10 border-b border-border px-3 align-middle text-text", className)}>{children}</td>;
}

/* ---------------- Skeleton / states ---------------- */

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton rounded-md", className)} aria-hidden />;
}

export function SkeletonRows({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="divide-y divide-border" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 px-3 py-3">
          {Array.from({ length: cols }).map((__, c) => (
            <Skeleton key={c} className={clsx("h-3.5", c === 0 ? "w-1/3" : "w-1/6")} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-3 grid size-9 place-items-center rounded-md border border-dashed border-border-strong text-muted">
        <svg viewBox="0 0 16 16" className="size-4" aria-hidden><path d="M3 5h10M3 8h10M3 11h6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
      </div>
      <p className="text-sm font-medium text-text">{title}</p>
      {description && <p className="mt-1 max-w-sm text-xs text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-danger">
      <span>{message}</span>
      {onRetry && <Button size="sm" variant="secondary" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

/* ---------------- Modal ---------------- */

export function Modal({ open, onClose, title, children, footer, wide }: {
  open: boolean; onClose: () => void; title: string; children: React.ReactNode; footer?: React.ReactNode; wide?: boolean;
}) {
  const id = useId();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const root = ref.current;
    (root?.querySelector<HTMLElement>("input,select,textarea") ?? root?.querySelector<HTMLElement>("button"))?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 pt-[8vh]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby={id}
        className={clsx("w-full rounded-lg border border-border bg-surface shadow-xl", wide ? "max-w-3xl" : "max-w-lg")}>
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 id={id} className="text-sm font-semibold">{title}</h2>
          <button onClick={onClose} className="rounded p-1 text-muted hover:bg-surface-2 hover:text-text" aria-label="Close">
            <svg viewBox="0 0 16 16" className="size-4"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-4 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-border px-4 py-3">{footer}</div>}
      </div>
    </div>
  );
}

/* ---------------- Misc ---------------- */

export function PageHeader({ title, description, actions }: { title: string; description?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="px-4 py-3">
      <div className="text-2xs font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="tabular mt-1 text-2xl font-semibold">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </div>
  );
}
