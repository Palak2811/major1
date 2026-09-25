import { Logo } from "./Logo";

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_minmax(420px,520px)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-border bg-surface-2 p-10 lg:flex">
        <Logo />
        <div className="max-w-md">
          <p className="text-2xl font-semibold leading-snug tracking-tight">
            Prepare for the company you want, not for a generic test.
          </p>
          <ul className="mt-6 space-y-3 text-sm text-text-2">
            {[
              ["Skill graph", "Mastery tracked per sub-topic, updated after every attempt."],
              ["Company-aware", "Practice mapped to each company’s observed assessment pattern."],
              ["Deterministic scoring", "Code is judged in a sandbox; readiness uses a fixed formula."],
            ].map(([h, d]) => (
              <li key={h} className="flex gap-3">
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-ochre" />
                <span><span className="font-medium text-text">{h}.</span> {d}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-muted">Final-year major project · Adaptive Placement Preparation Platform</p>
      </aside>
      <main className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-muted">{subtitle}</p>
          <div className="mt-6">{children}</div>
        </div>
      </main>
    </div>
  );
}

export function GoogleButton({ mock }: { mock: boolean }) {
  return (
    <div>
      <a href="/api/v1/auth/google/login"
        className="flex h-9 w-full items-center justify-center gap-2 rounded-md border border-border bg-surface text-sm font-medium hover:bg-surface-2">
        <svg viewBox="0 0 18 18" className="size-4" aria-hidden>
          <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z" />
          <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.83.86-3.04.86-2.34 0-4.33-1.58-5.04-3.7H.96v2.33A9 9 0 0 0 9 18z" />
          <path fill="#FBBC05" d="M3.96 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.28-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.05l3-2.33z" />
          <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 0 0 .96 4.95l3 2.33C4.67 5.16 6.66 3.58 9 3.58z" />
        </svg>
        Continue with Google
      </a>
      {mock && (
        <p className="mt-1.5 text-center text-2xs text-warn">
          Mock mode: GOOGLE_CLIENT_ID is not set, so this signs in a demo Google identity.
        </p>
      )}
    </div>
  );
}

export function Divider() {
  return (
    <div className="my-5 flex items-center gap-3 text-2xs uppercase tracking-wide text-muted">
      <span className="h-px flex-1 bg-border" />or<span className="h-px flex-1 bg-border" />
    </div>
  );
}
