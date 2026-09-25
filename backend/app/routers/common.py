"""Shared helpers for study and test routers."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Question, Submission, Topic, Verdict
from app.schemas import QuestionOut
from app.services.grading import GradeResult, is_answered


def public_question(q: Question) -> dict:
    """Question as a student may see it *before* answering (no key, no explanation)."""
    out = QuestionOut.model_validate(q).model_copy(update={"answer": None, "explanation": None})
    return out.model_dump(mode="json")


def reveal(q: Question) -> dict:
    """Answer key shown after an attempt. Hidden tests and reference code are never revealed."""
    key = {k: v for k, v in (q.answer or {}).items()
           if k not in ("hidden_tests", "reference_solution")}
    return {"answer": key, "explanation": q.explanation or ""}


async def subtree_topic_ids(db: AsyncSession, topic_id: int) -> list[int]:
    rows = (await db.execute(select(Topic.id, Topic.parent_id))).all()
    children: dict[int | None, list[int]] = {}
    for tid, pid in rows:
        children.setdefault(pid, []).append(tid)
    out, stack = [], [topic_id]
    while stack:
        t = stack.pop()
        out.append(t)
        stack.extend(children.get(t, []))
    return out


async def seen_counts(db: AsyncSession, user_id: int) -> dict[int, int]:
    rows = (await db.execute(
        select(Submission.question_id, func.count()).where(Submission.user_id == user_id,
                                                           Submission.mode != "run")
        .group_by(Submission.question_id))).all()
    return dict(rows)


def record(db: AsyncSession, *, user_id: int, attempt_id: int, q: Question, answer: dict | None,
           time_ms: int | None, g: GradeResult, marks: float | None = None,
           confidence: int | None = None) -> Submission:
    sub = Submission(user_id=user_id, attempt_id=attempt_id, question_id=q.id,
                     answer=answer or {}, time_taken_ms=time_ms, confidence=confidence,
                     language=(answer or {}).get("language"), code=(answer or {}).get("code"))
    if not is_answered(q.type, answer):
        status = "unanswered"
    else:
        status = "pending" if not g.gradable else "correct" if g.correct else "incorrect"
    sub.verdict = Verdict(status=status, is_correct=g.correct, judged_by=g.judged_by,
                          score=g.score if marks is None else marks,
                          details={"feedback": g.feedback, "fraction": g.score})
    db.add(sub)
    return sub
