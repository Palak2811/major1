"""Student progress: skill graph view and dashboard v1 — all derived from stored attempts."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_scopes
from app.models import (
    Attempt,
    Company,
    Profile,
    Question,
    Submission,
    Test,
    Topic,
    User,
    Verdict,
)
from app.models.base import as_utc, utcnow
from app.services.mastery import target_difficulty
from app.services.readiness_data import gather, report
from app.services.skill_graph import expected_time_ms, skill_tree
from app.services.verdicts import CORRECT, SCORED

router = APIRouter(prefix="/me", tags=["progress"])
AREAS = ["DSA", "DBMS", "OS", "CN", "OOP", "Aptitude"]


@router.get("/skills")
async def my_skills(user: User = Depends(require_scopes("me")),
                    db: AsyncSession = Depends(get_db)):
    nodes = await skill_tree(db, user.id)
    return [{
        "id": n.id, "name": n.name, "area": n.area, "parent_id": n.parent_id,
        "topic_id": n.topic_id,
        "mastery_score": n.own.mastery_score if n.own and n.own.attempt_count else None,
        "attempt_count": n.own.attempt_count if n.own else 0,
        "accuracy": n.own.accuracy if n.own and n.own.attempt_count else None,
        "average_time_ms": n.own.average_time_ms if n.own and n.own.attempt_count else None,
        "confidence": n.own.confidence if n.own else None,
        "difficulty": n.own.difficulty if n.own else None,
        "last_attempt": n.own.last_attempt if n.own else None,
        "rollup": n.rollup, "rollup_attempts": n.rollup_attempts,
        "next_difficulty": target_difficulty(n.own.mastery_score if n.own else None),
    } for n in nodes]


@router.get("/dashboard")
async def dashboard(user: User = Depends(require_scopes("me")),
                    db: AsyncSession = Depends(get_db)):
    nodes = await skill_tree(db, user.id)
    roots = {n.area: n for n in nodes if n.parent_id is None}
    areas = [{"area": a, "mastery": roots[a].rollup if a in roots else None,
              "attempts": roots[a].rollup_attempts if a in roots else 0} for a in AREAS]

    recent = []
    for a in (await db.scalars(select(Attempt).where(
            Attempt.user_id == user.id, Attempt.status != "in_progress")
            .order_by(Attempt.submitted_at.desc()).limit(8))).all():
        if a.mode == "test":
            t = await db.get(Test, a.test_id) if a.test_id else None
            title = t.title if t else "Deleted test"
        else:
            topic = await db.get(Topic, a.state.get("topic_id"))
            title = topic.name if topic else "Study session"
        recent.append({"id": a.id, "mode": a.mode, "title": title, "score": a.score,
                       "max_score": a.max_score, "submitted_at": a.submitted_at})

    since = utcnow() - timedelta(days=30)
    # Only answers that were actually given and scored (skipped test questions don't count).
    graded = select(Verdict).join(Submission).where(
        Submission.user_id == user.id, Submission.mode != "run", Verdict.status.in_(SCORED))
    total = await db.scalar(select(func.count()).select_from(graded.subquery())) or 0
    correct = await db.scalar(select(func.count()).select_from(
        graded.where(Verdict.status.in_(CORRECT)).subquery())) or 0
    last30 = await db.scalar(select(func.count()).select_from(
        graded.where(Submission.created_at >= since).subquery())) or 0

    p = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    return {
        "areas": areas,
        "recent_attempts": recent,
        "study_streak": p.study_streak if p else 0,
        "last_active_on": p.last_active_on if p else None,
        "questions_answered": total,
        "questions_answered_30d": last30,
        "overall_accuracy": round(correct / total, 4) if total else None,
        "weak_topics": p.weak_topics if p else [],
        "topics_completed": p.topics_completed if p else 0,
    }


# ---------------- Phase 3: readiness & analytics ----------------


async def _targets(db: AsyncSession, user: User) -> list[Company]:
    p = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    ids = (p.target_company_ids if p else None) or []
    stmt = select(Company).order_by(Company.name)
    if ids:
        stmt = stmt.where(Company.id.in_(ids))
    return list((await db.scalars(stmt)).all())


@router.get("/readiness")
async def my_readiness(company: str | None = None, user: User = Depends(require_scopes("me")),
                       db: AsyncSession = Depends(get_db)):
    """Consolidated readiness report (Equation 3.1): one company, or default weights."""
    c = None
    if company:
        c = await db.scalar(select(Company).where(
            Company.id == int(company) if company.isdigit() else Company.slug == company))
        if c is None:
            raise HTTPException(404, "Company not found")
    out = await report(db, user.id, c)
    await db.commit()
    return out


@router.get("/readiness/companies")
async def readiness_by_company(user: User = Depends(require_scopes("me")),
                               db: AsyncSession = Depends(get_db)):
    """Overall readiness for each target company (all companies if none are targeted)."""
    ev = await gather(db, user.id)
    out = []
    for c in await _targets(db, user):
        r = await report(db, user.id, c, ev=ev)
        out.append({"company_id": c.id, "name": c.name, "slug": c.slug, "overall": r["overall"],
                    "custom_weights": r["custom_weights"]})
    await db.commit()
    return out


@router.get("/analytics")
async def analytics(days: int = Query(30, ge=7, le=180),
                    user: User = Depends(require_scopes("me")),
                    db: AsyncSession = Depends(get_db)):
    """Everything the analytics dashboard plots, derived from stored submissions/verdicts."""
    subs = (await db.scalars(select(Submission).where(
        Submission.user_id == user.id, Submission.mode != "run")
        .order_by(Submission.created_at))).all()
    scored = [s for s in subs if s.verdict and s.verdict.status in SCORED]
    qids = {s.question_id for s in scored}
    qs = {q.id: q for q in (await db.scalars(
        select(Question).where(Question.id.in_(qids)))).unique().all()} if qids else {}

    # 1. accuracy over time (daily)
    start = (utcnow() - timedelta(days=days - 1)).date()
    daily = {start + timedelta(days=i): [0, 0] for i in range(days)}
    for s in scored:
        d = as_utc(s.created_at).date()
        if d in daily:
            daily[d][0] += 1
            daily[d][1] += s.verdict.status in CORRECT
    accuracy_series = [{"date": d.isoformat(), "answered": a, "correct": c,
                        "accuracy": round(c / a, 4) if a else None}
                       for d, (a, c) in daily.items()]

    # 2. topic mastery distribution, 6. weakest topics
    nodes = await skill_tree(db, user.id)
    practised = [n for n in nodes if n.topic_id and n.own and n.own.attempt_count]
    topic_mastery = sorted(({"topic": n.name, "area": n.area,
                             "mastery": round(n.own.mastery_score, 1),
                             "attempts": n.own.attempt_count} for n in practised),
                           key=lambda x: (x["area"], -x["mastery"]))
    weakest = sorted(({"topic": n.name, "area": n.area, "topic_id": n.topic_id,
                       "mastery": round(n.own.mastery_score, 1), "accuracy": n.own.accuracy,
                       "attempts": n.own.attempt_count, "confidence": n.own.confidence,
                       "last_attempt": n.own.last_attempt}
                      for n in practised), key=lambda x: x["mastery"])[:8]

    # 3. difficulty distribution of attempted (distinct) questions
    diff = {k: {"difficulty": k, "attempted": 0, "correct": 0} for k in ("easy", "medium", "hard")}
    solved: dict[int, bool] = {}
    for s in scored:
        solved[s.question_id] = solved.get(s.question_id, False) or s.verdict.status in CORRECT
    for qid, ok in solved.items():
        q = qs.get(qid)
        if q and q.difficulty in diff:
            diff[q.difficulty]["attempted"] += 1
            diff[q.difficulty]["correct"] += int(ok)

    # 4. time taken per question (latest 25 timed answers)
    timed = [s for s in scored if s.time_taken_ms and s.question_id in qs][-25:]
    time_per_q = [{"submission_id": s.id, "title": qs[s.question_id].title,
                   "difficulty": qs[s.question_id].difficulty, "type": qs[s.question_id].type,
                   "time_ms": s.time_taken_ms, "expected_ms": expected_time_ms(qs[s.question_id]),
                   "correct": s.verdict.status in CORRECT, "at": s.created_at} for s in timed]

    # 5. readiness across target companies (Equation 3.1 per company)
    ev = await gather(db, user.id)
    companies = []
    for c in await _targets(db, user):
        r = await report(db, user.id, c, ev=ev, save=False)
        companies.append({"company_id": c.id, "name": c.name, "slug": c.slug,
                          "overall": r["overall"],
                          **{x["key"]: x["value"] for x in r["components"]}})

    # self-reported confidence vs measured accuracy (kept since Phase 2)
    calibration = [{"topic": n.name, "confidence": round(n.own.confidence * 100, 1),
                    "accuracy": round(n.own.accuracy * 100, 1)}
                   for n in practised if n.own.confidence is not None]

    return {"accuracy_over_time": accuracy_series, "topic_mastery": topic_mastery,
            "difficulty_distribution": list(diff.values()), "time_per_question": time_per_q,
            "company_readiness": companies, "weakest_topics": weakest,
            "confidence_vs_accuracy": calibration, "total_scored": len(scored)}
