export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 font-semibold tracking-tight text-text">
      <svg viewBox="0 0 20 20" className="size-5 text-accent" aria-hidden>
        <path d="M3 16 L8 9 L11.5 12 L17 4" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="17" cy="4" r="1.8" fill="var(--ochre)" />
      </svg>
      {!compact && <span>PrepPath</span>}
    </span>
  );
}
