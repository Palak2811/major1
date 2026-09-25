"""The judging job: Submission → Judge0 → Verdict → Score → skill-graph update."""

from sqlalchemy import select

from app.models import Attempt, Question, Submission, Verdict
from app.services import jobs
from app.services.judge import (
    ACCEPTED,
    INTERNAL,
    MAX_CASES,
    VERDICT_LABEL,
    Case,
    Outcome,
    aggregate,
    get_judge,
)
from app.services.skill_graph import apply_evidence, refresh_profile

QUEUED, RUNNING = "queued", "running"


def build_cases(q: Question, mode: str, stdin: str | None) -> list[Case]:
    meta, key = q.meta or {}, q.answer or {}
    samples = [Case(s["input"], s["output"], True) for s in meta.get("samples", [])]
    if mode == "run":
        if stdin is not None:
            return [Case(stdin, None, True)]
        return samples
    hidden = [Case(t["input"], t["output"], False) for t in key.get("hidden_tests", [])]
    return (samples + hidden)[:MAX_CASES]


def sql_source(q: Question, query: str) -> str:
    meta = q.meta or {}
    return "\n".join([meta.get("schema_sql", ""), meta.get("seed_sql", ""), ".headers on",
                      ".mode list", query])


def public_details(o: Outcome, cases: list[Case], mode: str) -> dict:
    """Only visible cases expose input/output; hidden tests report pass counts only."""
    per_case = []
    for c, r in zip(cases, o.cases, strict=True):
        entry = {"verdict": r.verdict, "label": VERDICT_LABEL.get(r.verdict, r.verdict),
                 "time_s": r.time_s, "memory_kb": r.memory_kb, "visible": c.visible}
        if c.visible:
            entry |= {"stdin": c.stdin, "expected": c.expected, "stdout": r.stdout,
                      "stderr": r.stderr}
        per_case.append(entry)
    first_fail = next((i for i, (c, r) in enumerate(zip(cases, o.cases, strict=True))
                       if c.expected is not None and r.verdict != ACCEPTED), None)
    return {"mode": mode, "passed": o.passed, "total": o.total, "cases": per_case,
            "first_failed_case": first_fail, "max_time_s": o.max_time_s,
            "max_memory_kb": o.max_memory_kb, "compile_output": o.compile_output}


@jobs.job("judge_submission")
async def judge_submission(submission_id: int, stdin: str | None = None) -> None:
    async with jobs.session_factory() as db:
        sub = await db.get(Submission, submission_id)
        if sub is None or sub.verdict is None:
            return
        v: Verdict = sub.verdict
        q = await db.get(Question, sub.question_id)
        v.status = RUNNING
        await db.commit()

        meta = q.meta or {}
        time_limit = min(float(meta.get("time_limit_ms", 2000)) / 1000, 5.0)
        mem_limit = int(min(meta.get("memory_limit_mb", 256), 512) * 1024)
        judge = get_judge()
        try:
            if q.type == "sql":
                ref = await judge.execute("sql", sql_source(q, q.answer["reference_query"]),
                                          [Case("", None, False)], time_limit, mem_limit)
                expected = ref[0].stdout or ""
                cases = [Case("", expected, True)]
                outcome_raw = await judge.execute("sql", sql_source(q, sub.code or ""), cases,
                                                  time_limit, mem_limit)
            else:
                cases = build_cases(q, sub.mode, stdin)
                if not cases:
                    raise ValueError("Question has no test cases")
                outcome_raw = await judge.execute(sub.language, sub.code or "", cases,
                                                  time_limit, mem_limit)
            outcome = aggregate(outcome_raw, cases)
        except Exception as e:  # network / sandbox trouble: record, don't guess a verdict
            v.status = INTERNAL
            v.is_correct = False
            v.details = {**(v.details or {}), "error": f"{type(e).__name__}: {e}"[:500]}
            await db.commit()
            return

        # Judge0's verdict is final. Nothing below may change it.
        v.status = outcome.verdict
        v.is_correct = outcome.verdict == ACCEPTED
        v.details = {**(v.details or {}), **public_details(outcome, cases, sub.mode)}
        v.judged_by = "judge0"

        if sub.mode == "submit":
            v.score = 1.0 if v.is_correct else 0.0
            await apply_evidence(db, sub.user_id, q, v.is_correct, sub.time_taken_ms, None)
            await refresh_profile(db, sub.user_id)
        elif sub.mode == "test":
            marks = float(v.details.get("marks", 1.0))
            neg = float(v.details.get("negative_marks", 0.0))
            awarded = marks if v.is_correct else -neg
            v.score = awarded
            a = await db.get(Attempt, sub.attempt_id) if sub.attempt_id else None
            if a is not None:
                a.score = round((a.score or 0) + awarded, 2)
                a.max_score = (a.max_score or 0) + marks
            await apply_evidence(db, sub.user_id, q, v.is_correct, sub.time_taken_ms, None)
            await refresh_profile(db, sub.user_id, active=False)
        await db.commit()


async def pending_for_attempt(db, attempt_id: int) -> int:
    rows = (await db.scalars(select(Submission).where(Submission.attempt_id == attempt_id))).all()
    return sum(1 for s in rows if s.verdict and s.verdict.status in (QUEUED, RUNNING))
