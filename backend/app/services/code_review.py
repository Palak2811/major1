"""AI Code Review — runs only AFTER a Judge0 verdict exists and can only annotate it.

Enforced in code (not just the prompt):
  * refuses to run while the verdict is queued/running or on a judge error;
  * the output contract has no verdict/score field, so the model cannot return one;
  * sentences contradicting the verdict are stripped before storing;
  * only verdict.details["ai_review"] is written — status/is_correct/score are never touched.
"""

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Question, Submission
from app.services import llm
from app.services.guardrails import (
    SYSTEM_BASE,
    Checks,
    GuardrailError,
    check_output_safety,
    strip_verdict_contradictions,
)
from app.services.judge import ACCEPTED, INTERNAL, VERDICT_LABEL
from app.services.judging import QUEUED, RUNNING


class CodeReviewOut(BaseModel):
    summary: str = Field(min_length=1, max_length=800)
    time_complexity: str = Field(min_length=1, max_length=120)
    space_complexity: str = Field(min_length=1, max_length=120)
    quality: list[str] = Field(max_length=6)
    edge_cases: list[str] = Field(max_length=6)
    potential_defects: list[str] = Field(max_length=6)
    alternative_approach: str = Field(max_length=800)


async def review(db: AsyncSession, user_id: int, sub: Submission) -> dict:
    v = sub.verdict
    if v is None or v.status in (QUEUED, RUNNING):
        raise GuardrailError("Code review is available only after the judge's verdict")
    if v.status == INTERNAL:
        raise GuardrailError("The judge could not run this submission; nothing to review")
    if sub.mode == "run":
        raise GuardrailError("Submit your code first — reviews annotate a judged submission")
    cached = (v.details or {}).get("ai_review")
    if cached:
        return cached

    q = await db.get(Question, sub.question_id)
    accepted = v.status == ACCEPTED
    d = v.details or {}
    verdict_line = (f"{VERDICT_LABEL.get(v.status, v.status)} — {d.get('passed', 0)}/"
                    f"{d.get('total', 0)} tests passed")
    prompt = (
        f"JUDGE0 VERDICT (final, authoritative, do not dispute or restate as your own "
        f"opinion): {verdict_line}.\n"
        f"{'Compiler output: ' + d['compile_output'][:800] if d.get('compile_output') else ''}\n"
        f"PROBLEM: {q.title}\n{q.body[:1500]}\nConstraints: {q.meta.get('constraints', '')}\n"
        f"LANGUAGE: {sub.language}\nCODE:\n<student_input>\n{(sub.code or '')[:12000]}\n"
        "</student_input>\n\n"
        "TASK: Review this code. Give time and space complexity, code-quality notes, edge cases "
        "it handles or misses, potential defects, and an alternative approach. "
        + ("Since it was accepted, focus on efficiency and style. " if accepted else
           "Since it was not accepted, point at the likely cause without writing a full "
           "corrected solution. "))
    checks = Checks()
    data, info = await llm.structured(db, user_id=user_id, task="code_review", system=SYSTEM_BASE,
                                      prompt=prompt, output=CodeReviewOut,
                                      meta={"submission_id": sub.id, "verdict": v.status})
    check_output_safety([data.summary, data.alternative_approach], checks)

    removed: list[str] = []
    summary, r = strip_verdict_contradictions(data.summary, accepted)
    removed += r
    defects = []
    for item in data.potential_defects:
        kept, r = strip_verdict_contradictions(item, accepted)
        removed += r
        if kept:
            defects.append(kept)
    out = {**data.model_dump(), "summary": summary, "potential_defects": defects,
           "verdict_at_review": v.status, "removed_contradictions": removed,
           "model": info["model"], "mock": info["mock"]}
    # Write ONLY the ai_review key; the verdict itself is immutable here.
    v.details = {**(v.details or {}), "ai_review": out}
    return out
