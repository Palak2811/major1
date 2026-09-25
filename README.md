# PrepPath — AI-Powered Adaptive Placement Preparation Platform

Final-year major project. A company-aware, adaptive placement-prep platform with a hard
boundary between **deterministic evaluation** (Judge0 verdicts, the readiness formula) and
**generative AI** (explanations, tutoring, interviews).

| Phase | Scope | Status |
|---|---|---|
| 1 | Auth (email + Google), RBAC, full data model, question bank, company profiles, admin panel, design system | ✅ done |
| 2 | Skill graph + mastery updates, adaptive Study Mode, Test Mode, dashboard v1 | ✅ done |
| 3 | Monaco + Judge0 judge pipeline, Company Readiness Score (Eq. 3.1), analytics | ✅ done |
| 4 | RAG (pgvector HNSW), 6-mode AI tutor, guardrails + review queue, code review, resume/JD | ⏳ |
| 5 | 7-agent orchestration, mock interviews, adaptive roadmaps, notifications, production hardening | ⏳ |

## Stack

Next.js 15 (App Router, TypeScript, Tailwind v4) · FastAPI + Pydantic v2 · PostgreSQL + pgvector
(hosted, e.g. Neon free tier; SQLite fallback for local dev) · Redis (optional) · Celery ·
Judge0 CE (hosted sandbox) · Google Gemini (free tier) · GitHub Actions. **No Docker.**

```
frontend/   Next.js app (design system in src/app/globals.css, primitives in src/components/ui.tsx)
backend/    FastAPI app (app/), Alembic migrations, pytest suite
.github/    CI: lint → tests → frontend build
```

## Run locally

Requires Python 3.12+ and Node 22. Nothing else needs to be installed.

```bash
# 1. backend
cd backend
python -m venv .venv
.venv/Scripts/activate                  # Windows (source .venv/bin/activate on macOS/Linux)
pip install -r requirements-dev.txt
cp .env.example .env                    # optional: add keys (see below)
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000

# 2. frontend (second terminal)
cd frontend
npm install
npm run dev                             # http://localhost:3000 (proxies /api to :8000)
```

API docs: http://localhost:8000/api/docs.

## External services (all free, all optional)

| Service | Used for | Without it |
|---|---|---|
| **Neon** Postgres (`DATABASE_URL`) | Real pgvector + HNSW search | SQLite file `backend/dev.db`, vectors stored as JSON |
| **Google Gemini** free tier (`GEMINI_API_KEY`) | LLM (`gemini-flash-latest` / `gemini-flash-lite-latest`) + embeddings (`gemini-embedding-001`, 768-d) — Phase 4 | Labelled mock responses |
| **Judge0 CE** public instance `https://ce.judge0.com` (free, no key) | Sandboxed code execution — Phase 3 | Coding submissions can't be judged |
| **Upstash** Redis (`REDIS_URL`) | Cache, rate limiting, Celery broker | No cache / rate limits; background tasks run in-process |
| **Google OAuth** (`GOOGLE_CLIENT_ID/SECRET`) | Real Google sign-in | Labelled demo Google identity |

Submitted code never runs on this machine. It only ever goes to the Judge0 sandbox.

## Seeded accounts

| Role | Email | Password |
|---|---|---|
| Admin | `admin@preppath.dev` (env `SEED_ADMIN_EMAIL`) | `ChangeMe-Admin1` (env `SEED_ADMIN_PASSWORD`) |
| Content manager | `content@preppath.dev` | `ChangeMe-Content1` |
| Student | `student@preppath.dev` | `ChangeMe-Student1` |

The seed also creates the DSA/DBMS/OS/CN/OOP/Aptitude topic taxonomy, matching skill-graph nodes,
three company profiles (Amazon, TCS, Microsoft), ~57 published questions across all types (incl. 5 judged coding problems and 2 SQL problems), curated
explanations and worked examples for 12 topics, and a published two-section sample test.

## Environment variables

See [backend/.env.example](backend/.env.example). Nothing is required for a local run (set `JWT_SECRET` for anything shared). Anything that needs paid or external
credentials has a mock mode:

- **Google OAuth**: with `GOOGLE_CLIENT_ID` empty, "Continue with Google" signs in a fixed demo
  identity, and the login page says so.
- **LLM / embeddings**: with `GEMINI_API_KEY` empty, AI features return labelled mock output (Phase 4).

## Tests

```bash
cd backend && pytest -q          # 67 tests: auth/RBAC, content, mastery/grading, study/test flows, judge pipeline, Eq. 3.1
cd frontend && npm run build     # lint + typecheck + production build
```

Tests run against in-memory SQLite, so they need no services.

## Security model (Phase 1)

- Passwords: Argon2id (memory-hard, per-hash random salt).
- Access tokens: 15-minute JWT, kept in memory only on the client.
- Refresh tokens: random, stored only as a SHA-256 hash, sent as an httpOnly `SameSite=Lax` cookie
  scoped to `/api/v1/auth`, rotated on every use. Reusing a rotated token revokes the whole
  token family (theft detection).
- RBAC: roles `student` / `content_manager` / `admin` map to scopes (`me`, `content:read`,
  `content:write`, `admin:panel`, `users:manage`). The API returns **401** when unauthenticated and
  **403** on a missing scope. Scopes come from the user's current DB role, so a demotion takes effect
  immediately.
- Students never receive answers, explanations or hidden coding tests, and never see draft questions.
- Pydantic validation on every endpoint, ORM-only queries, a CORS allowlist, and secrets from
  env only. A Redis rate limiter is wired to the auth routes (active only when `REDIS_URL` and `RATE_LIMIT_ENABLED` are set).

## Phase 2: how learning is modelled

**Skill graph.** Every topic has a node (`skills`), arranged as DSA → Graphs → {BFS, DFS, …}
and likewise for DBMS, OS, CN, OOP and Aptitude. Each user has one `mastery` row per node with
`mastery_score, attempt_count, accuracy, average_time, difficulty, last_attempt, confidence`.
Parent and area scores are *rolled up*: the attempt-weighted mean over the subtree.

**Mastery update** ([app/services/mastery.py](backend/app/services/mastery.py)) is a pure,
deterministic function, fully unit-tested:

```
delta = lr · w · (target − mastery),  clipped to ±15, result clipped to [0, 100]
target = 100 if correct else 0;   lr = max(0.15, 1 / (attempts + 2))
w (correct) = difficulty weight (easy 0.7 · medium 1.0 · hard 1.3) × speed factor × confidence factor
w (wrong)   = (2 − difficulty weight) × (1 + 0.3 · confidence)   # confident mistakes cost more
```

**Study Mode loop:** Topic → Question → Explanation → Worked Example → Follow-up → Mini Quiz →
Confidence Check → Skill Update. The first question targets current mastery (easy < 35 ≤ medium
< 70 ≤ hard). The follow-up steps up after a correct answer and down after a wrong one. Mastery
is updated only when the cycle completes, so every update carries the self-rated confidence (1–5),
which is stored next to measured accuracy. Teaching content comes from a `ContentProvider`
([app/services/content.py](backend/app/services/content.py)). It currently serves curated
`documents`; Phase 4 swaps in a RAG provider behind the same interface.

**Test Mode:** sectioned tests with per-section time limits enforced *on the server*. A save after
a section's deadline is rejected, and an expired attempt auto-submits with its partial answers.
Other features: per-test negative marking, per-attempt randomised order, flag-for-review,
autosave, attempt history, and a post-attempt analysis (score, per-section and per-topic
breakdown, time per question, full review). `POST /tests/compose` builds tests with a balanced
difficulty mix and round-robin topic spread.

**Grading** ([app/services/grading.py](backend/app/services/grading.py)) is deterministic.
MCQ, multi-select, numerical (with tolerance) and output-prediction are graded exactly.
Debugging and theory use a clearly labelled keyword heuristic until Phase 4's Evaluate mode.
Coding and SQL are stored as **pending** and never executed in the backend; Judge0 scores them
in Phase 3.

Main endpoints: `POST /study/sessions`, `POST /study/sessions/{id}/answer`,
`POST /study/sessions/{id}/complete`, `GET/POST /tests`, `POST /tests/compose`,
`POST /tests/{id}/attempts`, `PUT /attempts/{id}/answers/{tq}`, `POST /attempts/{id}/submit`,
`GET /attempts/{id}/analysis`, `GET /me/skills`, `GET /me/dashboard`.

## Phase 3: code judging, readiness and analytics

**Submission pipeline** (code never runs in the API process):

```
Monaco editor → POST /api/v1/submissions (validate, persist verdict=queued) → 202 + id
  → job queue (Celery if REDIS_URL is set, else an in-process task after the response)
  → Judge0 CE batch (each case sent with expected_output, so Judge0 decides the verdict)
  → Verdict (Accepted / Wrong Answer / TLE / Compilation Error / Runtime Error)
  → score → skill-graph mastery update → readiness
client polls GET /api/v1/submissions/{id}
```

- Languages: Python 3.13, C++ (GCC 14), Java 13, JavaScript (Node 22); SQL runs on Judge0's SQLite,
  with the user's output compared against the reference query's output.
- **Run** checks the visible samples (or custom stdin) and never affects mastery. **Submit** runs
  samples plus hidden tests. Hidden inputs and outputs are never returned to the client.
- Coding and SQL answers inside a timed test are queued on submission. Their marks, including
  negative marks, are added to the attempt when the verdict arrives.
- A Judge0 outage is recorded as `internal_error` and scores nothing; no verdict is ever guessed.
- One in-flight submission per student, to stay polite to the free public Judge0 instance.
- Every seeded hidden test was verified by running reference solutions on the real Judge0.

**Company Readiness Score** ([app/services/readiness.py](backend/app/services/readiness.py)),
a pure function with hand-computed unit tests:

```
readiness = 0.25·DSA + 0.20·CSF + 0.20·Coding + 0.15·Aptitude + 0.10·Interview + 0.10·Consistency
```

| Component | Source (0–100) |
|---|---|
| DSA | 0.7 × DSA skill-graph mastery + 0.3 × accepted ratio of DSA coding problems |
| CS fundamentals | attempt-weighted mastery across DBMS / OS / CN / OOP |
| Coding | 70 × accepted ratio (distinct problems, Judge0 verdicts) + 30 × solve-speed score |
| Aptitude | accuracy on Aptitude-area answers |
| Interview | **0, shown as "Phase 5"**: the mock-interview agent doesn't exist yet, so nothing is estimated |
| Consistency | 50 × min(streak, 14)/14 + 50 × active days in the last 14 / 14 |

Company profiles can override the weights (they must sum to 1). A snapshot is stored whenever the
score changes, and those snapshots feed the history sparkline.

**Readiness report** (`/readiness/{company}`): overall %, per-domain breakdown with evidence,
biggest weaknesses weighted by the company's observed emphasis, and a rule-based next step.

**Analytics** (`/analytics`, Recharts): accuracy over time, topic mastery distribution, difficulty
distribution, time per question, readiness across target companies, and a ranked weakest-topics
list. Each chart has a table view. All values come from `GET /me/analytics`.

## Company data disclaimer

Company OA patterns and skill weights are **observed historical preparation patterns, not official
specifications**. The API returns this text as `pattern_disclaimer` on every company, and the UI
shows it wherever company pattern data appears.
