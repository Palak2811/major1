"""Code submissions.

Flow: POST /submissions → validate + persist (verdict=queued) → enqueue → 202 with id.
A background job sends the code to Judge0 and writes the verdict; clients poll
GET /submissions/{id}. Code is never executed by the API process.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_scopes
from app.core.ratelimit import rate_limit
from app.models import Question, Submission, User, Verdict
from app.services import jobs
from app.services.judge import CODE_LANGUAGES, LANGUAGES, VERDICT_LABEL
from app.services.judging import QUEUED, RUNNING

router = APIRouter(prefix="/submissions", tags=["submissions"])

MAX_CODE = 64 * 1024
MAX_STDIN = 16 * 1024


class SubmissionIn(BaseModel):
    question_id: int
    language: Literal["python", "cpp", "java", "javascript", "sql"]
    code: str = Field(min_length=1, max_length=MAX_CODE)
    mode: Literal["run", "submit"] = "submit"
    stdin: str | None = Field(default=None, max_length=MAX_STDIN)
    time_taken_ms: int | None = Field(default=None, ge=0, le=24 * 3600 * 1000)

    @model_validator(mode="after")
    def stdin_only_for_run(self):
        if self.stdin is not None and self.mode != "run":
            raise ValueError("Custom stdin is only allowed for run")
        return self


def view(s: Submission) -> dict:
    v = s.verdict
    return {
        "id": s.id, "question_id": s.question_id, "mode": s.mode, "language": s.language,
        "code": s.code, "time_taken_ms": s.time_taken_ms, "created_at": s.created_at,
        "verdict": None if v is None else {
            "status": v.status, "label": VERDICT_LABEL.get(v.status, v.status.title()),
            "is_correct": v.is_correct, "done": v.status not in (QUEUED, RUNNING),
            "judged_by": v.judged_by, "details": v.details or {},
        },
    }


@router.post("", status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(rate_limit(30, 60, "submissions"))])
async def create(body: SubmissionIn, user: User = Depends(require_scopes("me")),
                 db: AsyncSession = Depends(get_db)):
    q = await db.get(Question, body.question_id)
    if q is None or q.status != "published":
        raise HTTPException(404, "Question not found")
    if q.type not in ("coding", "sql"):
        raise HTTPException(422, "Only coding and SQL questions are judged")
    if q.type == "sql" and body.language != "sql":
        raise HTTPException(422, "SQL questions must be submitted as sql")
    if q.type == "coding" and body.language not in CODE_LANGUAGES:
        raise HTTPException(422, f"Language must be one of {', '.join(CODE_LANGUAGES)}")
    if q.type == "sql" and body.mode == "run" and body.stdin:
        raise HTTPException(422, "SQL runs take no stdin")

    # Public Judge0 is shared and rate-limited: one in-flight job per student.
    inflight = await db.scalar(select(Submission.id).join(Verdict).where(
        Submission.user_id == user.id, Verdict.status.in_((QUEUED, RUNNING))).limit(1))
    if inflight:
        raise HTTPException(429, "You already have a submission being judged — wait for its "
                                 "verdict first")

    s = Submission(user_id=user.id, question_id=q.id, mode=body.mode, language=body.language,
                   code=body.code, answer={}, time_taken_ms=body.time_taken_ms)
    s.verdict = Verdict(status=QUEUED, is_correct=False, score=0.0, judged_by="judge0",
                        details={"language_label": LANGUAGES[body.language][1]})
    db.add(s)
    await db.commit()
    jobs.enqueue("judge_submission", submission_id=s.id, stdin=body.stdin)
    return view(s)


@router.get("/{submission_id}")
async def get(submission_id: int, user: User = Depends(require_scopes("me")),
              db: AsyncSession = Depends(get_db)):
    s = await db.get(Submission, submission_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(404, "Submission not found")
    await db.refresh(s, ["verdict"])
    return view(s)


@router.get("")
async def history(question_id: int | None = None,
                  mode: Literal["run", "submit", "test"] | None = None,
                  limit: int = Query(20, ge=1, le=100),
                  user: User = Depends(require_scopes("me")), db: AsyncSession = Depends(get_db)):
    stmt = select(Submission).where(Submission.user_id == user.id,
                                    Submission.mode.in_(("run", "submit", "test")))
    if question_id:
        stmt = stmt.where(Submission.question_id == question_id)
    if mode:
        stmt = stmt.where(Submission.mode == mode)
    rows = (await db.scalars(stmt.order_by(Submission.created_at.desc()).limit(limit))).all()
    return [view(s) for s in rows]


@router.post("/{submission_id}/review")
async def code_review(submission_id: int, user: User = Depends(require_scopes("me")),
                      db: AsyncSession = Depends(get_db)):
    """AI code review — only after a Judge0 verdict; annotates, never overrides it."""
    from app.routers.ai import guarded
    from app.services import code_review as cr

    s = await db.get(Submission, submission_id)
    if s is None or s.user_id != user.id:
        raise HTTPException(404, "Submission not found")
    await db.refresh(s, ["verdict"])
    review = await guarded(db, cr.review(db, user.id, s))
    return {"submission": view(s), "review": review}
