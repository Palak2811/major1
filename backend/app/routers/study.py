"""Adaptive Study Mode.

Loop: Topic → Question → Explanation → Worked Example → Follow-up → Mini Quiz
      → Confidence Check → Skill State Update.

Difficulty adapts twice: the first question targets the student's current mastery, and
the follow-up steps up after a correct answer (or holds/steps down after a wrong one).
Mastery is only updated when the cycle completes, so every update carries the
self-reported confidence alongside measured correctness.
"""

import random
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_scopes
from app.models import Attempt, Mastery, Question, Submission, Topic, User
from app.models.base import utcnow
from app.routers.common import public_question, record, reveal, seen_counts, subtree_topic_ids
from app.services.content import get_provider
from app.services.grading import AUTO_TYPES, HEURISTIC_TYPES, grade
from app.services.mastery import target_difficulty
from app.services.skill_graph import apply_evidence, refresh_profile, skill_for_topic

router = APIRouter(prefix="/study", tags=["study"])

STUDY_TYPES = AUTO_TYPES | HEURISTIC_TYPES
LEVELS = ["easy", "medium", "hard"]
QUIZ_SIZE = 3


class StartIn(BaseModel):
    topic_id: int


class AnswerIn(BaseModel):
    question_id: int
    answer: dict = Field(default_factory=dict)
    time_taken_ms: int = Field(ge=0, le=3_600_000)


class CompleteIn(BaseModel):
    confidence: int = Field(ge=1, le=5)


def _shift(level: str, by: int) -> str:
    return LEVELS[max(0, min(2, LEVELS.index(level) + by))]


def _pick(pool: list[Question], level: str, exclude: set[int], seen: dict[int, int],
          rng: random.Random) -> Question | None:
    cands = [q for q in pool if q.id not in exclude]
    if not cands:
        return None
    rng.shuffle(cands)
    # least-seen first, then closest difficulty
    cands.sort(key=lambda q: (seen.get(q.id, 0),
                              abs(LEVELS.index(q.difficulty) - LEVELS.index(level))))
    return cands[0]


async def _pool(db: AsyncSession, topic: Topic) -> list[Question]:
    ids = await subtree_topic_ids(db, topic.id)
    stmt = select(Question).where(Question.status == "published",
                                  Question.type.in_(STUDY_TYPES))
    pool = list((await db.scalars(stmt.where(Question.topic_id.in_(ids)))).unique().all())
    if len(pool) < 2 + QUIZ_SIZE and topic.parent_id:  # widen to the parent topic's subtree
        ids = await subtree_topic_ids(db, topic.parent_id)
        pool = list((await db.scalars(stmt.where(Question.topic_id.in_(ids)))).unique().all())
    return pool


async def _session(db: AsyncSession, user: User, session_id: int) -> Attempt:
    a = await db.get(Attempt, session_id)
    if a is None or a.user_id != user.id or a.mode != "study":
        raise HTTPException(404, "Study session not found")
    return a


def _order(st: dict) -> list[int]:
    return [x for x in [st["primary_id"], st.get("followup_id"), *st.get("quiz_ids", [])] if x]


def _stage(st: dict, status: str) -> str:
    if status == "completed":
        return "done"
    answered = st["answers"]
    if str(st["primary_id"]) not in answered:
        return "question"
    if st.get("followup_id") and str(st["followup_id"]) not in answered:
        return "followup"
    if any(str(q) not in answered for q in st.get("quiz_ids", [])):
        return "quiz"
    return "confidence"


async def _view(db: AsyncSession, a: Attempt) -> dict:
    st = a.state
    qs = {q.id: q for q in (await db.scalars(
        select(Question).where(Question.id.in_(_order(st))))).unique().all()}
    topic = await db.get(Topic, st["topic_id"])
    return {
        "id": a.id,
        "status": a.status,
        "stage": _stage(st, a.status),
        "topic": {"id": topic.id, "name": topic.name, "area": topic.area} if topic else None,
        "mastery_before": st["mastery_before"],
        "target_difficulty": st["target_difficulty"],
        "question": public_question(qs[st["primary_id"]]),
        "explanation": st.get("explanation"),
        "worked_example": st.get("worked_example"),
        "followup": public_question(qs[st["followup_id"]]) if st.get("followup_id") else None,
        "quiz": [public_question(qs[i]) for i in st.get("quiz_ids", []) if i in qs],
        "answers": st["answers"],
        "confidence": st.get("confidence"),
        "result": st.get("result"),
        "started_at": a.started_at,
    }


@router.post("/sessions", status_code=201)
async def start(body: StartIn, user: User = Depends(require_scopes("me")),
                db: AsyncSession = Depends(get_db)):
    topic = await db.get(Topic, body.topic_id)
    if topic is None:
        raise HTTPException(404, "Topic not found")
    pool = await _pool(db, topic)
    if not pool:
        raise HTTPException(422, "No published practice questions for this topic yet")

    skill = await skill_for_topic(db, topic.id)
    m = await db.scalar(select(Mastery).where(Mastery.user_id == user.id,
                                              Mastery.skill_id == skill.id)) if skill else None
    mastery = m.mastery_score if m and m.attempt_count else None
    level = target_difficulty(mastery)
    rng = random.Random()
    primary = _pick(pool, level, set(), await seen_counts(db, user.id), rng)

    provider = get_provider()
    blocks = {k: await provider.teach(db, topic, k) for k in ("explanation", "worked_example")}
    a = Attempt(user_id=user.id, mode="study", status="in_progress", state={
        "topic_id": topic.id,
        "mastery_before": mastery,
        "target_difficulty": level,
        "primary_id": primary.id,
        "followup_id": None,
        "quiz_ids": [],
        "answers": {},
        "explanation": asdict(blocks["explanation"]) if blocks["explanation"] else None,
        "worked_example": asdict(blocks["worked_example"]) if blocks["worked_example"] else None,
    })
    db.add(a)
    await db.commit()
    return await _view(db, a)


@router.get("/sessions/{session_id}")
async def get_session(session_id: int, user: User = Depends(require_scopes("me")),
                      db: AsyncSession = Depends(get_db)):
    return await _view(db, await _session(db, user, session_id))


@router.post("/sessions/{session_id}/teach/{kind}")
async def teach(session_id: int, kind: str, user: User = Depends(require_scopes("me")),
                db: AsyncSession = Depends(get_db)):
    """RAG-grounded explanation / worked example for the session's topic.

    Goes through the full guardrail pipeline. If AI is unavailable or the knowledge base has
    nothing on the topic, the curated block stays in place and the response says why.
    """
    from app.services import llm, tutor
    from app.services.guardrails import GuardrailError

    if kind not in ("explanation", "worked_example"):
        raise HTTPException(404, "Unknown teaching block")
    a = await _session(db, user, session_id)
    st = dict(a.state)
    cached = st.get(f"ai_{kind}")
    if cached:
        return {"block": cached, "fallback": False}
    topic = await db.get(Topic, st["topic_id"])
    try:
        env = await tutor.teach_topic(db, user.id, topic, kind)
    except (GuardrailError, llm.AIError) as e:
        await db.commit()  # keep the trace of the failed call
        return {"block": st.get(kind), "fallback": True, "reason": str(e)}
    if not env["grounded"]:
        await db.commit()
        return {"block": st.get(kind), "fallback": True,
                "reason": "AI answer cited no retrieved source, so it was not shown"}
    block = tutor.block_to_teaching(env, kind)
    st[f"ai_{kind}"] = block
    a.state = st
    await db.commit()
    return {"block": block, "fallback": False}


@router.post("/sessions/{session_id}/answer")
async def answer(session_id: int, body: AnswerIn, user: User = Depends(require_scopes("me")),
                 db: AsyncSession = Depends(get_db)):
    a = await _session(db, user, session_id)
    if a.status != "in_progress":
        raise HTTPException(409, "Session already completed")
    st = dict(a.state)
    answers = dict(st["answers"])
    stage = _stage(st, a.status)
    if stage == "question":
        allowed = {st["primary_id"]}
    elif stage == "followup":
        allowed = {st["followup_id"]}
    elif stage == "quiz":
        allowed = {q for q in st.get("quiz_ids", []) if str(q) not in answers}
    else:
        allowed = set()
    if body.question_id not in allowed:
        raise HTTPException(409, f"Question {body.question_id} can't be answered at stage "
                                 f"'{stage}'")

    q = await db.get(Question, body.question_id)
    g = grade(q.type, q.answer, body.answer)
    record(db, user_id=user.id, attempt_id=a.id, q=q, answer=body.answer,
           time_ms=body.time_taken_ms, g=g)
    answers[str(q.id)] = {"correct": g.correct, "score": g.score, "gradable": g.gradable,
                          "judged_by": g.judged_by, "feedback": g.feedback,
                          "time_ms": body.time_taken_ms, "response": body.answer, **reveal(q)}
    st["answers"] = answers

    if q.id == st["primary_id"]:
        # Adaptive follow-up: step up after a correct answer, step down after a wrong one.
        topic = await db.get(Topic, st["topic_id"])
        pool = await _pool(db, topic)
        seen = await seen_counts(db, user.id)
        rng = random.Random()
        level = _shift(q.difficulty, 1 if g.correct else -1)
        fu = _pick(pool, level, {q.id}, seen, rng)
        st["followup_id"] = fu.id if fu else None
        taken = {q.id} | ({fu.id} if fu else set())
        quiz: list[int] = []
        for _ in range(QUIZ_SIZE):
            nxt = _pick(pool, st["target_difficulty"], taken, seen, rng)
            if not nxt:
                break
            quiz.append(nxt.id)
            taken.add(nxt.id)
        st["quiz_ids"] = quiz
        st["followup_level"] = level

    a.state = st
    await db.commit()
    return await _view(db, a)


@router.post("/sessions/{session_id}/complete")
async def complete(session_id: int, body: CompleteIn, user: User = Depends(require_scopes("me")),
                   db: AsyncSession = Depends(get_db)):
    a = await _session(db, user, session_id)
    if a.status != "in_progress":
        raise HTTPException(409, "Session already completed")
    st = dict(a.state)
    if _stage(st, a.status) != "confidence":
        raise HTTPException(409, "Answer every question in the cycle before the confidence check")

    changes: dict[int, dict] = {}
    score = max_score = 0.0
    for qid in _order(st):
        ans = st["answers"][str(qid)]
        if not ans["gradable"]:
            continue
        q = await db.get(Question, qid)
        ch = await apply_evidence(db, user.id, q, ans["correct"], ans["time_ms"], body.confidence)
        score += ans["score"]
        max_score += 1
        if ch:
            prev = changes.get(ch.skill_id)
            changes[ch.skill_id] = {"skill_id": ch.skill_id, "skill": ch.skill_name,
                                    "before": prev["before"] if prev else ch.before,
                                    "after": ch.after}
    subs = (await db.scalars(select(Submission).where(Submission.attempt_id == a.id))).all()
    for s in subs:
        s.confidence = body.confidence
    await refresh_profile(db, user.id)

    st["confidence"] = body.confidence
    st["result"] = {"changes": list(changes.values()), "score": score, "max_score": max_score}
    a.state = st
    a.status = "completed"
    a.score, a.max_score = score, max_score
    a.submitted_at = utcnow()
    await db.commit()
    return await _view(db, a)
