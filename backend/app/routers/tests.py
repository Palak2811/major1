"""Test Mode: authoring, balanced composition, timed attempts, grading and analysis.

Timing is enforced server-side. Sections run sequentially; each has a deadline derived from
the attempt start. Saves after a section's deadline are rejected, and an attempt past its
final deadline is auto-submitted (partial answers kept) the next time it is touched.
"""

import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_scopes
from app.models import (
    Attempt,
    Company,
    Question,
    Submission,
    Test,
    TestQuestion,
    Topic,
    User,
    Verdict,
)
from app.models.base import as_utc, utcnow
from app.routers.common import public_question, record, reveal, subtree_topic_ids
from app.schemas import QuestionType
from app.services import jobs
from app.services.composition import Candidate, balance
from app.services.grading import SANDBOX_TYPES, grade, is_answered
from app.services.judging import QUEUED
from app.services.skill_graph import apply_evidence, refresh_profile
from app.services.verdicts import outcome as verdict_outcome

router = APIRouter(tags=["tests"])
GRACE = timedelta(seconds=5)


# ---------------- schemas ----------------


class SectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    time_limit_seconds: int | None = Field(default=None, ge=60, le=4 * 3600)


class TestQuestionIn(BaseModel):
    question_id: int
    section: str = "General"
    marks: float = Field(default=1.0, gt=0, le=100)


class TestSettings(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    company_id: int | None = None
    duration_seconds: int = Field(default=3600, ge=60, le=6 * 3600)
    sections: list[SectionIn] = Field(default_factory=lambda: [SectionIn(name="General")],
                                      min_length=1, max_length=10)
    negative_marking: bool = False
    negative_ratio: float = Field(default=0.25, ge=0, le=1)
    randomize: bool = True
    is_published: bool = False

    @model_validator(mode="after")
    def unique_sections(self):
        names = [s.name for s in self.sections]
        if len(set(names)) != len(names):
            raise ValueError("Section names must be unique")
        limits = [s.time_limit_seconds for s in self.sections]
        if any(limits) and not all(limits):
            raise ValueError("Either every section has a time limit or none does")
        return self


class TestCreate(TestSettings):
    questions: list[TestQuestionIn] = Field(min_length=1, max_length=200)


class DifficultyMix(BaseModel):
    easy: float = Field(default=0.3, ge=0)
    medium: float = Field(default=0.5, ge=0)
    hard: float = Field(default=0.2, ge=0)


class ComposeSection(SectionIn):
    topic_ids: list[int] = Field(min_length=1, max_length=50)
    count: int = Field(ge=1, le=100)
    types: list[QuestionType] | None = None
    marks: float = Field(default=1.0, gt=0, le=100)


class TestCompose(TestSettings):
    sections: list[ComposeSection] = Field(min_length=1, max_length=10)  # type: ignore[assignment]
    mix: DifficultyMix = Field(default_factory=DifficultyMix)
    seed: int | None = None


class TestPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    is_published: bool | None = None


class SaveIn(BaseModel):
    answer: dict | None = None
    time_spent_ms: int = Field(default=0, ge=0, le=6 * 3600 * 1000)  # delta since last save
    flagged: bool | None = None


# ---------------- helpers ----------------


def _can_write(u: User) -> bool:
    return "content:write" in (u.role.scopes or [])


async def _tqs(db: AsyncSession, test_id: int) -> list[TestQuestion]:
    return list((await db.scalars(select(TestQuestion).where(TestQuestion.test_id == test_id)
                                  .order_by(TestQuestion.position))).all())


async def _summary(db: AsyncSession, t: Test, user: User | None = None) -> dict:
    tqs = await _tqs(db, t.id)
    company = await db.get(Company, t.company_id) if t.company_id else None
    out = {
        "id": t.id, "title": t.title, "description": t.description,
        "company": {"id": company.id, "name": company.name} if company else None,
        "duration_seconds": _total_duration(t), "sections": t.sections,
        "negative_marking": t.negative_marking, "randomize": t.randomize,
        "is_published": t.is_published, "question_count": len(tqs),
        "total_marks": sum(tq.marks for tq in tqs), "created_at": t.created_at,
    }
    if user:
        a = await db.scalar(select(Attempt).where(
            Attempt.user_id == user.id, Attempt.test_id == t.id, Attempt.status == "in_progress"))
        out["active_attempt_id"] = a.id if a else None
    return out


def _total_duration(t: Test) -> int:
    limits = [s.get("time_limit_seconds") for s in t.sections]
    return sum(limits) if limits and all(limits) else t.duration_seconds


async def _save_test(db: AsyncSession, body: TestSettings, items: list[TestQuestionIn],
                     user: User) -> Test:
    if body.company_id and not await db.get(Company, body.company_id):
        raise HTTPException(422, "Unknown company_id")
    section_names = {s.name for s in body.sections}
    qids = [i.question_id for i in items]
    if len(set(qids)) != len(qids):
        raise HTTPException(422, "A question appears twice in the test")
    found = {q.id: q for q in (await db.scalars(
        select(Question).where(Question.id.in_(qids)))).unique().all()}
    for i in items:
        if i.question_id not in found:
            raise HTTPException(422, f"Unknown question {i.question_id}")
        if found[i.question_id].status != "published":
            raise HTTPException(422, f"Question {i.question_id} is not published")
        if i.section not in section_names:
            raise HTTPException(422, f"Unknown section '{i.section}'")
    t = Test(title=body.title, description=body.description, company_id=body.company_id,
             duration_seconds=body.duration_seconds,
             sections=[s.model_dump(include={"name", "time_limit_seconds"})
                       for s in body.sections],
             negative_marking=body.negative_marking, randomize=body.randomize,
             is_published=body.is_published, created_by=user.id)
    db.add(t)
    await db.flush()
    order = {s.name: n for n, s in enumerate(body.sections)}
    for pos, i in enumerate(sorted(items, key=lambda i: order[i.section])):
        db.add(TestQuestion(
            test_id=t.id, question_id=i.question_id, section=i.section, position=pos,
            marks=i.marks,
            negative_marks=round(i.marks * body.negative_ratio, 2) if body.negative_marking else 0))
    await db.commit()
    return t


def _deadlines(t: Test, started: datetime) -> tuple[list[dict], datetime]:
    started = as_utc(started)
    limits = [s.get("time_limit_seconds") for s in t.sections]
    out, cursor = [], started
    if limits and all(limits):
        for s in t.sections:
            cursor = cursor + timedelta(seconds=s["time_limit_seconds"])
            out.append({"name": s["name"], "deadline": cursor.isoformat()})
        return out, cursor
    end = started + timedelta(seconds=t.duration_seconds)
    return [{"name": s["name"], "deadline": end.isoformat()} for s in t.sections], end


async def _attempt(db: AsyncSession, user: User, attempt_id: int) -> Attempt:
    a = await db.get(Attempt, attempt_id)
    if a is None or a.user_id != user.id or a.mode != "test":
        raise HTTPException(404, "Attempt not found")
    return a


async def _finalize(db: AsyncSession, a: Attempt, auto: bool) -> list[int]:
    """Grade objective answers now; queue coding/SQL answers for Judge0.

    Returns submission ids to enqueue *after* the caller commits. Judged marks are added to
    the attempt's score (and max score) by the judging job when the verdict arrives.
    """
    to_judge: list[Submission] = []
    t = await db.get(Test, a.test_id)
    tqs = {tq.id: tq for tq in await _tqs(db, t.id)}
    st = dict(a.state)
    answers = st.get("answers", {})
    score = max_score = 0.0
    for tq_id in st["order"]:
        tq = tqs.get(tq_id)
        if tq is None:
            continue
        q = await db.get(Question, tq.question_id)
        saved = answers.get(str(tq_id), {})
        resp = saved.get("answer")
        answered = is_answered(q.type, resp)
        if q.type in SANDBOX_TYPES and answered:
            code = resp.get("code") or resp.get("text") or ""
            lang = "sql" if q.type == "sql" else resp.get("language") or "python"
            sub = Submission(user_id=a.user_id, attempt_id=a.id, question_id=q.id, mode="test",
                             answer=resp, language=lang, code=code,
                             time_taken_ms=saved.get("time_ms") or None)
            sub.verdict = Verdict(status=QUEUED, is_correct=False, score=0.0, judged_by="judge0",
                                  details={"tq_id": tq.id, "marks": tq.marks,
                                           "negative_marks": tq.negative_marks})
            db.add(sub)
            to_judge.append(sub)
            continue
        g = grade(q.type, q.answer, resp)
        if not g.gradable:
            marks = 0.0
        else:
            max_score += tq.marks
            marks = tq.marks if g.correct else (-tq.negative_marks if answered else 0.0)
        score += marks
        record(db, user_id=a.user_id, attempt_id=a.id, q=q, answer=resp,
               time_ms=saved.get("time_ms") or None, g=g, marks=marks)
        if g.gradable and answered:
            await apply_evidence(db, a.user_id, q, g.correct, saved.get("time_ms") or None, None)
    await refresh_profile(db, a.user_id)
    st["auto_submitted"] = auto
    a.state = st
    a.status = "submitted"
    a.score, a.max_score = round(score, 2), max_score
    a.submitted_at = utcnow()
    await db.flush()
    return [sub.id for sub in to_judge]


async def _expire_if_due(db: AsyncSession, a: Attempt) -> bool:
    if a.status == "in_progress":
        deadline = datetime.fromisoformat(a.state["deadline"])
        if utcnow() > deadline + GRACE:
            ids = await _finalize(db, a, auto=True)
            await db.commit()
            for sid in ids:
                jobs.enqueue("judge_submission", submission_id=sid)
            return True
    return False


async def _attempt_view(db: AsyncSession, a: Attempt) -> dict:
    t = await db.get(Test, a.test_id)
    tqs = {tq.id: tq for tq in await _tqs(db, t.id)}
    qs = {q.id: q for q in (await db.scalars(select(Question).where(
        Question.id.in_([tq.question_id for tq in tqs.values()])))).unique().all()}
    return {
        "id": a.id, "status": a.status, "test": await _summary(db, t),
        "started_at": a.started_at, "server_now": utcnow(),
        "deadline": a.state["deadline"], "sections": a.state["sections"],
        "items": [{"tq_id": i, "section": tqs[i].section, "marks": tqs[i].marks,
                   "negative_marks": tqs[i].negative_marks,
                   "question": public_question(qs[tqs[i].question_id])}
                  for i in a.state["order"] if i in tqs],
        "answers": a.state.get("answers", {}),
        "score": a.score, "max_score": a.max_score,
        "auto_submitted": a.state.get("auto_submitted", False),
    }


# ---------------- authoring ----------------


@router.get("/tests")
async def list_tests(user: User = Depends(require_scopes("content:read")),
                     db: AsyncSession = Depends(get_db)):
    stmt = select(Test).order_by(Test.created_at.desc())
    if not _can_write(user):
        stmt = stmt.where(Test.is_published.is_(True))
    return [await _summary(db, t, user) for t in (await db.scalars(stmt)).all()]


@router.get("/tests/{test_id}")
async def get_test(test_id: int, user: User = Depends(require_scopes("content:read")),
                   db: AsyncSession = Depends(get_db)):
    t = await db.get(Test, test_id)
    if t is None or (not t.is_published and not _can_write(user)):
        raise HTTPException(404, "Test not found")
    out = await _summary(db, t, user)
    if _can_write(user):
        tqs = await _tqs(db, t.id)
        qs = {q.id: q for q in (await db.scalars(select(Question).where(
            Question.id.in_([tq.question_id for tq in tqs])))).unique().all()}
        out["items"] = [{"tq_id": tq.id, "section": tq.section, "marks": tq.marks,
                         "negative_marks": tq.negative_marks,
                         "question": public_question(qs[tq.question_id])} for tq in tqs]
    return out


@router.post("/tests", status_code=201)
async def create_test(body: TestCreate, user: User = Depends(require_scopes("content:write")),
                      db: AsyncSession = Depends(get_db)):
    t = await _save_test(db, body, body.questions, user)
    return await get_test(t.id, user, db)


@router.post("/tests/compose", status_code=201)
async def compose_test(body: TestCompose, user: User = Depends(require_scopes("content:write")),
                       db: AsyncSession = Depends(get_db)):
    """Build a test per section from topic pools with a balanced difficulty mix."""
    rng = random.Random(body.seed)
    used: set[int] = set()
    items: list[TestQuestionIn] = []
    for sec in body.sections:
        topic_ids: set[int] = set()
        for tid in sec.topic_ids:
            if not await db.get(Topic, tid):
                raise HTTPException(422, f"Unknown topic {tid}")
            topic_ids.update(await subtree_topic_ids(db, tid))
        stmt = select(Question).where(Question.status == "published",
                                      Question.topic_id.in_(topic_ids))
        if sec.types:
            stmt = stmt.where(Question.type.in_(sec.types))
        pool = [Candidate(q.id, q.difficulty, q.topic_id)
                for q in (await db.scalars(stmt)).unique().all() if q.id not in used]
        picked = balance(pool, sec.count, body.mix.model_dump(), rng)
        if len(picked) < sec.count:
            raise HTTPException(422, f"Section '{sec.name}' needs {sec.count} questions but only "
                                     f"{len(picked)} published questions match")
        used.update(c.id for c in picked)
        items += [TestQuestionIn(question_id=c.id, section=sec.name, marks=sec.marks)
                  for c in picked]
    t = await _save_test(db, body, items, user)
    return await get_test(t.id, user, db)


@router.patch("/tests/{test_id}")
async def patch_test(test_id: int, body: TestPatch,
                     user: User = Depends(require_scopes("content:write")),
                     db: AsyncSession = Depends(get_db)):
    t = await db.get(Test, test_id)
    if t is None:
        raise HTTPException(404, "Test not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await db.commit()
    return await get_test(t.id, user, db)


@router.delete("/tests/{test_id}", status_code=204)
async def delete_test(test_id: int, _: User = Depends(require_scopes("content:write")),
                      db: AsyncSession = Depends(get_db)):
    t = await db.get(Test, test_id)
    if t is None:
        raise HTTPException(404, "Test not found")
    for tq in await _tqs(db, t.id):
        await db.delete(tq)
    await db.delete(t)
    await db.commit()


# ---------------- attempts ----------------


@router.post("/tests/{test_id}/attempts", status_code=201)
async def start_attempt(test_id: int, user: User = Depends(require_scopes("me")),
                        db: AsyncSession = Depends(get_db)):
    t = await db.get(Test, test_id)
    if t is None or not t.is_published:
        raise HTTPException(404, "Test not found")
    existing = await db.scalar(select(Attempt).where(
        Attempt.user_id == user.id, Attempt.test_id == t.id, Attempt.status == "in_progress"))
    if existing and not await _expire_if_due(db, existing):
        return await _attempt_view(db, existing)  # resume

    tqs = await _tqs(db, t.id)
    rng = random.Random()
    order: list[int] = []
    for s in t.sections:  # randomise within each section, keep section order
        ids = [tq.id for tq in tqs if tq.section == s["name"]]
        if t.randomize:
            rng.shuffle(ids)
        order += ids
    started = utcnow()
    sections, deadline = _deadlines(t, started)
    a = Attempt(user_id=user.id, test_id=t.id, mode="test", status="in_progress",
                started_at=started, max_score=sum(tq.marks for tq in tqs),
                state={"order": order, "sections": sections, "deadline": deadline.isoformat(),
                       "answers": {}})
    db.add(a)
    await db.commit()
    return await _attempt_view(db, a)


@router.get("/attempts")
async def my_attempts(mode: str | None = None, limit: int = Query(50, ge=1, le=200),
                      user: User = Depends(require_scopes("me")),
                      db: AsyncSession = Depends(get_db)):
    stmt = select(Attempt).where(Attempt.user_id == user.id)
    if mode:
        stmt = stmt.where(Attempt.mode == mode)
    rows = (await db.scalars(stmt.order_by(Attempt.started_at.desc()).limit(limit))).all()
    out = []
    for a in rows:
        if a.mode == "test":
            await _expire_if_due(db, a)
        title = None
        if a.test_id:
            t = await db.get(Test, a.test_id)
            title = t.title if t else "Deleted test"
        elif a.mode == "study":
            topic = await db.get(Topic, a.state.get("topic_id"))
            title = f"Study · {topic.name}" if topic else "Study session"
        out.append({"id": a.id, "mode": a.mode, "status": a.status, "title": title,
                    "test_id": a.test_id, "score": a.score, "max_score": a.max_score,
                    "started_at": a.started_at, "submitted_at": a.submitted_at})
    return out


@router.get("/attempts/{attempt_id}")
async def get_attempt(attempt_id: int, user: User = Depends(require_scopes("me")),
                      db: AsyncSession = Depends(get_db)):
    a = await _attempt(db, user, attempt_id)
    await _expire_if_due(db, a)
    return await _attempt_view(db, a)


@router.put("/attempts/{attempt_id}/answers/{tq_id}")
async def save_answer(attempt_id: int, tq_id: int, body: SaveIn,
                      user: User = Depends(require_scopes("me")),
                      db: AsyncSession = Depends(get_db)):
    a = await _attempt(db, user, attempt_id)
    if await _expire_if_due(db, a):
        raise HTTPException(409, "Time is up — the attempt was auto-submitted")
    if a.status != "in_progress":
        raise HTTPException(409, "Attempt already submitted")
    if tq_id not in a.state["order"]:
        raise HTTPException(404, "Question not in this attempt")
    tq = await db.get(TestQuestion, tq_id)
    sec = next(s for s in a.state["sections"] if s["name"] == tq.section)
    if utcnow() > datetime.fromisoformat(sec["deadline"]) + GRACE:
        raise HTTPException(409, f"Section '{tq.section}' has ended")
    st = dict(a.state)
    answers = dict(st.get("answers", {}))
    cur = dict(answers.get(str(tq_id), {"answer": None, "time_ms": 0, "flagged": False}))
    if body.answer is not None:
        cur["answer"] = body.answer
    if body.flagged is not None:
        cur["flagged"] = body.flagged
    cur["time_ms"] = cur.get("time_ms", 0) + body.time_spent_ms
    answers[str(tq_id)] = cur
    st["answers"] = answers
    a.state = st
    await db.commit()
    return {"tq_id": tq_id, **cur}


@router.post("/attempts/{attempt_id}/submit")
async def submit_attempt(attempt_id: int, user: User = Depends(require_scopes("me")),
                         db: AsyncSession = Depends(get_db)):
    a = await _attempt(db, user, attempt_id)
    if a.status == "in_progress" and not await _expire_if_due(db, a):
        ids = await _finalize(db, a, auto=False)
        await db.commit()
        for sid in ids:
            jobs.enqueue("judge_submission", submission_id=sid)
    return await analysis(attempt_id, user, db)


@router.get("/attempts/{attempt_id}/analysis")
async def analysis(attempt_id: int, user: User = Depends(require_scopes("me")),
                   db: AsyncSession = Depends(get_db)):
    a = await _attempt(db, user, attempt_id)
    await _expire_if_due(db, a)
    if a.status == "in_progress":
        raise HTTPException(409, "Submit the attempt to see its analysis")
    t = await db.get(Test, a.test_id)
    tqs = {tq.id: tq for tq in await _tqs(db, t.id)}
    subs = {s.question_id: s for s in (await db.scalars(
        select(Submission).where(Submission.attempt_id == a.id))).all()}
    saved = a.state.get("answers", {})
    items, sections, topics = [], {}, {}
    counts = {"correct": 0, "incorrect": 0, "unanswered": 0, "pending": 0}
    for i in a.state["order"]:
        tq = tqs.get(i)
        if tq is None:
            continue
        q = await db.get(Question, tq.question_id)
        sub = subs.get(q.id)
        v = sub.verdict if sub else None
        status = verdict_outcome(v.status if v else None)
        counts[status] += 1
        marks = v.score if v else 0.0
        time_ms = saved.get(str(i), {}).get("time_ms", 0)
        items.append({
            "tq_id": i, "section": tq.section, "question_id": q.id, "title": q.title,
            "type": q.type, "difficulty": q.difficulty,
            "topic": q.topic.name if q.topic else None, "status": status,
            "judged_by": v.judged_by if v else None,
            "verdict": v.status if v else None,
            "judge": {k: (v.details or {}).get(k) for k in
                      ("passed", "total", "max_time_s", "max_memory_kb", "compile_output")}
            if v and v.judged_by == "judge0" else None,
            "feedback": (v.details or {}).get("feedback", "") if v else "",
            "marks": tq.marks, "awarded": marks, "time_ms": time_ms,
            "flagged": saved.get(str(i), {}).get("flagged", False),
            "response": saved.get(str(i), {}).get("answer"),
            "question": public_question(q), **reveal(q),
        })
        for bucket, key in ((sections, tq.section), (topics, q.topic.name if q.topic else "—")):
            b = bucket.setdefault(key, {"name": key, "awarded": 0.0, "max": 0.0, "correct": 0,
                                        "attempted": 0, "time_ms": 0})
            b["awarded"] += marks
            b["max"] += 0 if status == "pending" else tq.marks
            b["correct"] += status == "correct"
            b["attempted"] += status in ("correct", "incorrect")
            b["time_ms"] += time_ms
    graded = counts["correct"] + counts["incorrect"]
    return {
        "attempt_id": a.id, "test": await _summary(db, t), "status": a.status,
        "auto_submitted": a.state.get("auto_submitted", False),
        "score": a.score, "max_score": a.max_score,
        "started_at": a.started_at, "submitted_at": a.submitted_at,
        "counts": counts, "accuracy": round(counts["correct"] / graded, 4) if graded else None,
        "total_time_ms": sum(it["time_ms"] for it in items),
        "sections": list(sections.values()), "topics": list(topics.values()), "items": items,
    }


@router.get("/tests/{test_id}/stats", tags=["admin"])
async def test_stats(test_id: int, _: User = Depends(require_scopes("content:write")),
                     db: AsyncSession = Depends(get_db)):
    n = await db.scalar(select(func.count(Attempt.id)).where(
        Attempt.test_id == test_id, Attempt.status == "submitted"))
    avg = await db.scalar(select(func.avg(Attempt.score)).where(
        Attempt.test_id == test_id, Attempt.status == "submitted"))
    return {"submitted_attempts": n or 0, "average_score": round(avg, 2) if avg else None}
