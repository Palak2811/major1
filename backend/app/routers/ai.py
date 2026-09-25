"""AI endpoints: tutor modes, question generation + review queue, observability."""

from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_scopes
from app.models import AITrace, Question, User
from app.schemas import QuestionOut
from app.services import generation, llm, tutor
from app.services.guardrails import GuardrailError

router = APIRouter(prefix="/ai", tags=["ai"])


async def guarded(db: AsyncSession, coro):
    """Commit traces even on failure; map errors to honest HTTP responses."""
    try:
        out = await coro
        await db.commit()
        return out
    except llm.BudgetExceeded as e:
        await db.commit()
        raise HTTPException(429, str(e)) from None
    except GuardrailError as e:
        await db.commit()
        raise HTTPException(422, str(e)) from None
    except llm.AIError as e:
        await db.commit()
        status = 429 if "rate limit" in str(e) else 503
        raise HTTPException(status, f"AI unavailable: {e}") from None


# ---------------- tutor (6 bounded modes) ----------------


class ExplainIn(BaseModel):
    question: str = Field(min_length=1, max_length=800)
    topic_id: int | None = None
    company_id: int | None = None


class HintIn(BaseModel):
    question_id: int
    attempt: str | None = Field(default=None, max_length=2000)


class InterviewerIn(BaseModel):
    company_id: int | None = None
    topic_id: int | None = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class EvaluateIn(BaseModel):
    question: str = Field(min_length=1, max_length=1500)
    answer: str = Field(min_length=1, max_length=4000)
    expected_concepts: list[str] | None = Field(default=None, max_length=8)
    question_id: int | None = None


class FollowupIn(BaseModel):
    previous_question: str = Field(min_length=1, max_length=1500)
    previous_answer: str = Field(min_length=1, max_length=3000)
    topic_id: int | None = None


class RevisionIn(BaseModel):
    limit: int = Field(default=3, ge=1, le=5)


@router.post("/tutor/explain")
async def t_explain(body: ExplainIn, user: User = Depends(require_scopes("me")),
                    db: AsyncSession = Depends(get_db)):
    return await guarded(db, tutor.explain(db, user.id, body.question, body.topic_id,
                                           body.company_id))


@router.post("/tutor/hint")
async def t_hint(body: HintIn, user: User = Depends(require_scopes("me")),
                 db: AsyncSession = Depends(get_db)):
    return await guarded(db, tutor.hint(db, user.id, body.question_id, body.attempt))


@router.post("/tutor/interviewer")
async def t_interviewer(body: InterviewerIn, user: User = Depends(require_scopes("me")),
                        db: AsyncSession = Depends(get_db)):
    return await guarded(db, tutor.interviewer(db, user.id, body.company_id, body.difficulty,
                                               body.topic_id))


@router.post("/tutor/evaluate")
async def t_evaluate(body: EvaluateIn, user: User = Depends(require_scopes("me")),
                     db: AsyncSession = Depends(get_db)):
    return await guarded(db, tutor.evaluate(db, user.id, body.question, body.answer,
                                            body.expected_concepts, body.question_id))


@router.post("/tutor/followup")
async def t_followup(body: FollowupIn, user: User = Depends(require_scopes("me")),
                     db: AsyncSession = Depends(get_db)):
    return await guarded(db, tutor.followup(db, user.id, body.previous_question,
                                            body.previous_answer, body.topic_id))


@router.post("/tutor/revision")
async def t_revision(body: RevisionIn, user: User = Depends(require_scopes("me")),
                     db: AsyncSession = Depends(get_db)):
    return await guarded(db, tutor.revision(db, user.id, body.limit))


@router.get("/status")
async def status(_: User = Depends(require_scopes("me"))):
    from app.core.config import get_settings

    s = get_settings()
    return {"provider": "mock" if llm.is_mock() else "gemini", "mock": llm.is_mock(),
            "fast_model": s.llm_model_fast, "strong_model": s.llm_model_strong,
            "embedding_model": s.embedding_model}


# ---------------- generation + review queue ----------------


class GenerateIn(BaseModel):
    topic_id: int
    type: Literal["mcq", "coding"] = "mcq"
    difficulty: Literal["easy", "medium", "hard"] = "medium"


def _review_view(q: Question) -> dict:
    out = QuestionOut.model_validate(q).model_dump(mode="json")
    out["answer"], out["explanation"] = q.answer, q.explanation
    out["review"] = (q.meta or {}).get("review", {})
    return out


@router.post("/questions/generate", status_code=201)
async def generate_question(body: GenerateIn, user: User = Depends(require_scopes("content:write")),
                            db: AsyncSession = Depends(get_db)):
    q = await guarded(db, generation.generate(db, user_id=user.id, topic_id=body.topic_id,
                                              qtype=body.type, difficulty=body.difficulty))
    await db.refresh(q)
    return _review_view(q)


@router.get("/review-queue")
async def review_queue(state: Literal["pending", "rejected", "all"] = "pending",
                       _: User = Depends(require_scopes("content:write")),
                       db: AsyncSession = Depends(get_db)):
    stmt = select(Question).where(Question.source == "ai")
    if state == "pending":
        stmt = stmt.where(Question.status == "review")
    elif state == "rejected":
        stmt = stmt.where(Question.status == "rejected")
    rows = (await db.scalars(stmt.order_by(Question.created_at.desc()))).unique().all()
    return [_review_view(q) for q in rows]


class ReviewDecision(BaseModel):
    note: str = Field(default="", max_length=500)


async def _ai_question(db: AsyncSession, qid: int) -> Question:
    q = await db.get(Question, qid)
    if q is None or q.source != "ai":
        raise HTTPException(404, "AI-generated question not found")
    return q


@router.post("/review-queue/{question_id}/approve")
async def approve(question_id: int, body: ReviewDecision,
                  user: User = Depends(require_scopes("content:write")),
                  db: AsyncSession = Depends(get_db)):
    q = await _ai_question(db, question_id)
    if q.status != "review":
        raise HTTPException(409, f"Question is '{q.status}', not awaiting review")
    ok, why = generation.can_publish(q)
    if not ok:
        raise HTTPException(409, why)
    review = {**q.meta["review"], "status": "approved", "decided_by": user.id,
              "note": body.note}
    q.meta = {**q.meta, "review": review}
    q.status = "published"
    await db.commit()
    await db.refresh(q)
    return _review_view(q)


@router.post("/review-queue/{question_id}/reject")
async def reject(question_id: int, body: ReviewDecision,
                 user: User = Depends(require_scopes("content:write")),
                 db: AsyncSession = Depends(get_db)):
    q = await _ai_question(db, question_id)
    if q.status == "published":
        raise HTTPException(409, "Already published — archive it from the question bank instead")
    q.meta = {**q.meta, "review": {**q.meta["review"], "status": "rejected",
                                   "decided_by": user.id, "note": body.note}}
    q.status = "rejected"
    await db.commit()
    await db.refresh(q)
    return _review_view(q)


@router.post("/review-queue/{question_id}/revalidate")
async def revalidate(question_id: int, _: User = Depends(require_scopes("content:write")),
                     db: AsyncSession = Depends(get_db)):
    """Re-run the Judge0 consistency check (e.g. after the sandbox was unreachable)."""
    q = await _ai_question(db, question_id)
    if q.type != "coding" or q.status != "review":
        raise HTTPException(409, "Only coding questions awaiting review can be revalidated")
    generation.jobs.enqueue("validate_generated_coding", question_id=q.id)
    return {"queued": True}


# ---------------- observability ----------------


@router.get("/stats")
async def ai_stats(days: int = Query(7, ge=1, le=90),
                   _: User = Depends(require_scopes("admin:panel")),
                   db: AsyncSession = Depends(get_db)):
    """Latency, token usage, estimated cost and failure rate per AI call type."""
    rows = (await db.scalars(select(AITrace).where(AITrace.created_at >= llm.since(days)))).all()
    agg: dict[str, dict] = defaultdict(lambda: {"calls": 0, "failures": 0, "cache_hits": 0,
                                                "latencies": [], "prompt_tokens": 0,
                                                "completion_tokens": 0, "cost_usd": 0.0})
    for r in rows:
        a = agg[r.call_type]
        a["calls"] += 1
        a["failures"] += not r.success
        a["cache_hits"] += (r.meta or {}).get("cache") == "hit"
        if r.success and (r.meta or {}).get("cache") != "hit":
            a["latencies"].append(r.latency_ms)
        a["prompt_tokens"] += r.prompt_tokens
        a["completion_tokens"] += r.completion_tokens
        a["cost_usd"] += r.cost_usd
    out = []
    for k, a in sorted(agg.items()):
        lat = sorted(a.pop("latencies"))
        out.append({"call_type": k, **a, "cost_usd": round(a["cost_usd"], 5),
                    "failure_rate": round(a["failures"] / a["calls"], 4) if a["calls"] else 0,
                    "avg_latency_ms": round(sum(lat) / len(lat)) if lat else None,
                    "p95_latency_ms": lat[int(0.95 * (len(lat) - 1))] if lat else None})
    recent = [{"id": r.id, "call_type": r.call_type, "model": r.model, "latency_ms": r.latency_ms,
               "tokens": r.prompt_tokens + r.completion_tokens, "success": r.success,
               "error": r.error, "created_at": r.created_at}
              for r in sorted(rows, key=lambda r: r.created_at, reverse=True)[:25]]
    return {"days": days, "by_type": out, "recent": recent, "mock": llm.is_mock()}
