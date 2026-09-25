"""Gather Equation 3.1 components from stored attempts (DB side of readiness)."""

from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Profile, Question, ReadinessScore, Submission
from app.models.base import as_utc, utcnow
from app.schemas import PATTERN_DISCLAIMER
from app.services.readiness import (
    COMPONENTS,
    CONSISTENCY_WINDOW_DAYS,
    DEFAULT_WEIGHTS,
    LABELS,
    accuracy_component,
    coding_component,
    consistency_component,
    contributions,
    dsa_component,
    rank_weaknesses,
    readiness,
)
from app.services.skill_graph import CSF_AREAS, area_mastery, expected_time_ms, skill_tree
from app.services.verdicts import CORRECT, SCORED

COMPANY_AREA = {"dsa": "DSA", "oop": "OOP", "dbms": "DBMS", "os": "OS", "aptitude": "Aptitude"}
DEFAULT_EMPHASIS = {"DSA": 25, "DBMS": 5, "OS": 5, "CN": 5, "OOP": 5, "Aptitude": 15}


@dataclass
class Evidence:
    components: dict[str, float]
    available: dict[str, bool]
    detail: dict[str, str]
    nodes: list = field(default_factory=list)
    unsolved_coding: list[tuple[int, str]] = field(default_factory=list)


async def _scored_submissions(db: AsyncSession, user_id: int):
    subs = (await db.scalars(select(Submission).where(
        Submission.user_id == user_id, Submission.mode != "run"))).all()
    subs = [s for s in subs if s.verdict and s.verdict.status in SCORED]
    qids = {s.question_id for s in subs}
    qs = {q.id: q for q in (await db.scalars(
        select(Question).where(Question.id.in_(qids)))).unique().all()} if qids else {}
    return subs, qs


async def gather(db: AsyncSession, user_id: int) -> Evidence:
    nodes = await skill_tree(db, user_id)
    areas = area_mastery(nodes)
    subs, qs = await _scored_submissions(db, user_id)

    # ---- coding (Judge0 verdicts only) ----
    attempted: set[int] = set()
    accepted: set[int] = set()
    dsa_attempted: set[int] = set()
    dsa_accepted: set[int] = set()
    best_speed: dict[int, float] = {}
    for s in subs:
        q = qs.get(s.question_id)
        if q is None or q.type != "coding" or s.verdict.judged_by != "judge0":
            continue
        is_dsa = q.topic is not None and q.topic.area == "DSA"
        attempted.add(q.id)
        if is_dsa:
            dsa_attempted.add(q.id)
        if s.verdict.status in CORRECT:
            accepted.add(q.id)
            if is_dsa:
                dsa_accepted.add(q.id)
            if s.time_taken_ms:
                speed = min(1.0, expected_time_ms(q) / max(s.time_taken_ms, 1))
                best_speed[q.id] = max(best_speed.get(q.id, 0.0), speed)
    dsa_ratio = len(dsa_accepted) / len(dsa_attempted) if dsa_attempted else None

    # ---- aptitude accuracy ----
    apt = [s for s in subs if (q := qs.get(s.question_id)) and q.topic and
           q.topic.area == "Aptitude"]
    apt_correct = sum(s.verdict.status in CORRECT for s in apt)

    # ---- consistency ----
    p = await db.scalar(select(Profile).where(Profile.user_id == user_id))
    since = utcnow() - timedelta(days=CONSISTENCY_WINDOW_DAYS)
    active_days = {as_utc(s.created_at).date() for s in subs if as_utc(s.created_at) >= since}
    streak = p.study_streak if p and p.last_active_on and \
        (utcnow().date() - p.last_active_on).days <= 1 else 0

    csf = [(areas[a][0], areas[a][1]) for a in CSF_AREAS if a in areas]
    csf_value = sum(v * w for v, w in csf) / sum(w for _, w in csf) if csf else None
    dsa_m = areas.get("DSA", (None, 0))[0]

    comps = {
        "dsa": dsa_component(dsa_m, dsa_ratio),
        "csf": csf_value or 0.0,
        "coding": coding_component(len(attempted), len(accepted), list(best_speed.values())),
        "aptitude": accuracy_component(apt_correct, len(apt)),
        "interview": 0.0,
        "consistency": consistency_component(streak, len(active_days)),
    }
    available = {
        "dsa": dsa_m is not None or dsa_ratio is not None,
        "csf": csf_value is not None,
        "coding": bool(attempted),
        "aptitude": bool(apt),
        "interview": False,
        "consistency": bool(active_days) or streak > 0,
    }
    detail = {
        "dsa": (f"DSA mastery {round(dsa_m)}" if dsa_m is not None else "No DSA practice yet")
        + (f"; {len(dsa_accepted)}/{len(dsa_attempted)} DSA coding problems accepted"
           if dsa_attempted else ""),
        "csf": "Mastery across " + ", ".join(f"{a} {round(areas[a][0])}" for a in CSF_AREAS
                                             if a in areas) if csf else
        "No DBMS / OS / CN / OOP practice yet",
        "coding": f"{len(accepted)}/{len(attempted)} problems accepted by Judge0"
        if attempted else "No judged coding submissions yet",
        "aptitude": f"{apt_correct}/{len(apt)} aptitude answers correct" if apt
        else "No aptitude answers yet",
        "interview": "Mock interviews arrive in Phase 5 — scored 0 until then, not estimated",
        "consistency": f"Streak {streak} day(s); active {len(active_days)} of the last "
                       f"{CONSISTENCY_WINDOW_DAYS} days",
    }
    all_coding = (await db.scalars(select(Question).where(
        Question.type == "coding", Question.status == "published"))).unique().all()
    unsolved = [(q.id, q.title) for q in all_coding if q.id not in accepted]
    return Evidence({k: round(v, 2) for k, v in comps.items()}, available, detail, nodes, unsolved)


def weights_for(company: Company | None) -> dict[str, float]:
    return dict(company.readiness_weights) if company and company.readiness_weights \
        else dict(DEFAULT_WEIGHTS)


def recommend(ev: Evidence, weights: dict[str, float], weaknesses) -> dict:
    """Rule-based next step: close the component with the largest weighted gap."""
    gaps = {k: weights[k] * (100 - ev.components[k]) for k in COMPONENTS if k != "interview"}
    worst = max(gaps, key=gaps.get)
    by_area = {"dsa": {"DSA"}, "csf": set(CSF_AREAS), "aptitude": {"Aptitude"}}
    if worst in by_area:
        w = next((w for w in weaknesses if w.area in by_area[worst]), None)
        topic = next((n for n in ev.nodes if w and n.name == w.name and n.topic_id), None)
        if w and topic:
            return {"component": worst, "title": f"Study {w.name}",
                    "detail": f"{LABELS[worst]} is your largest weighted gap; {w.name} "
                              f"({w.reason}).", "action": "study", "topic_id": topic.topic_id}
        return {"component": worst, "title": f"Practise {LABELS[worst]}",
                "detail": f"{LABELS[worst]} is your largest weighted gap.", "action": "study"}
    if worst == "coding":
        if ev.unsolved_coding:
            qid, title = ev.unsolved_coding[0]
            return {"component": "coding", "title": f"Solve “{title}”",
                    "detail": "Coding performance is your largest weighted gap.",
                    "action": "code", "question_id": qid}
        return {"component": "coding", "title": "Re-solve a problem faster",
                "detail": "All problems accepted; solve time now drives this component.",
                "action": "code"}
    return {"component": "consistency", "title": "Complete a study cycle today",
            "detail": "Regular practice is your largest weighted gap.", "action": "study"}


async def report(db: AsyncSession, user_id: int, company: Company | None,
                 ev: Evidence | None = None, save: bool = True) -> dict:
    ev = ev or await gather(db, user_id)
    w = weights_for(company)
    overall = readiness(ev.components, w)
    contrib = contributions(ev.components, w)
    if company:
        emphasis = {COMPANY_AREA[k]: v for k, v in (company.skill_weights or {}).items()
                    if k in COMPANY_AREA}
        frequent = set((company.oa_pattern or {}).get("frequent_topics", []))
    else:
        emphasis, frequent = DEFAULT_EMPHASIS, set()
    # Leaf topics use their own mastery. A parent topic appears only while its whole subtree is
    # unpractised (a frequently-tested area never touched); otherwise its children speak for it.
    has_children = {n.parent_id for n in ev.nodes}
    leaves = []
    for n in ev.nodes:
        if not n.topic_id:
            continue
        if n.id in has_children:
            if n.rollup_attempts == 0:
                leaves.append((n.name, n.area, None, 0))
            continue
        leaves.append((n.name, n.area, n.own.mastery_score if n.own and n.own.attempt_count
                       else None, n.own.attempt_count if n.own else 0))
    weaknesses = rank_weaknesses(leaves, emphasis, frequent)

    history = []
    if save:
        same = (ReadinessScore.company_id == company.id if company
                else ReadinessScore.company_id.is_(None))
        last = await db.scalar(select(ReadinessScore).where(
            ReadinessScore.user_id == user_id, same)
            .order_by(ReadinessScore.computed_at.desc()).limit(1))
        if last is None or abs(last.overall - overall) >= 0.01 or last.weights != w:
            db.add(ReadinessScore(user_id=user_id, company_id=company.id if company else None,
                                  overall=overall, components=ev.components, weights=w))
            await db.flush()
        rows = (await db.scalars(select(ReadinessScore).where(
            ReadinessScore.user_id == user_id, same)
            .order_by(ReadinessScore.computed_at.desc()).limit(30))).all()
        history = [{"at": r.computed_at, "overall": r.overall} for r in reversed(rows)]

    return {
        "company": {"id": company.id, "name": company.name, "slug": company.slug,
                    "pattern_disclaimer": PATTERN_DISCLAIMER} if company else None,
        "overall": overall,
        "formula": "0.25·DSA + 0.20·CSF + 0.20·Coding + 0.15·Aptitude + 0.10·Interview "
                   "+ 0.10·Consistency" if w == DEFAULT_WEIGHTS else "company-specific weights",
        "custom_weights": w != DEFAULT_WEIGHTS,
        "components": [{"key": k, "label": LABELS[k], "value": ev.components[k],
                        "weight": w[k], "contribution": contrib[k],
                        "available": ev.available[k], "detail": ev.detail[k]}
                       for k in COMPONENTS],
        "weaknesses": [w_.__dict__ for w_ in weaknesses],
        "recommendation": recommend(ev, w, weaknesses),
        "history": history,
    }
