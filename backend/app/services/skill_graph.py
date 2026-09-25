"""Skill-graph persistence: map questions to skill nodes, apply mastery updates,
roll mastery up the hierarchy, and refresh the profile's competence fields."""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Mastery, Profile, Question, Skill, Topic
from app.models.base import as_utc, utcnow
from app.services.composition import next_streak
from app.services.mastery import DEFAULT_EXPECTED_MS, Evidence, SkillState, update_mastery

CSF_AREAS = ("DBMS", "OS", "CN", "OOP")
WEAK_THRESHOLD = 40.0
COMPLETE_THRESHOLD = 70.0


async def skill_for_topic(db: AsyncSession, topic_id: int | None) -> Skill | None:
    """Every topic has a skill node; create it lazily (e.g. for admin-created topics)."""
    if topic_id is None:
        return None
    sk = await db.scalar(select(Skill).where(Skill.topic_id == topic_id))
    if sk:
        return sk
    topic = await db.get(Topic, topic_id)
    if topic is None:
        return None
    parent = await skill_for_topic(db, topic.parent_id) if topic.parent_id else None
    if parent is None:
        parent = await db.scalar(select(Skill).where(Skill.slug == topic.area.lower(),
                                                     Skill.topic_id.is_(None)))
        if parent is None:
            parent = Skill(name=topic.area, slug=topic.area.lower(), area=topic.area)
            db.add(parent)
            await db.flush()
    sk = Skill(name=topic.name, slug=f"t-{topic.slug}", area=topic.area, topic_id=topic.id,
               parent_id=parent.id)
    db.add(sk)
    await db.flush()
    return sk


def expected_time_ms(q: Question) -> int:
    base = int(q.meta.get("expected_time_ms") or DEFAULT_EXPECTED_MS.get(q.difficulty, 120_000))
    return base * 5 if q.type == "coding" else base


def _to_state(m: Mastery) -> SkillState:
    return SkillState(m.mastery_score, m.attempt_count, m.correct_count, m.accuracy,
                      m.average_time_ms, m.confidence,
                      as_utc(m.last_attempt) if m.last_attempt else None)


@dataclass
class MasteryChange:
    skill_id: int
    skill_name: str
    before: float
    after: float


async def apply_evidence(db: AsyncSession, user_id: int, q: Question, correct: bool,
                         time_ms: int | None, confidence: int | None) -> MasteryChange | None:
    sk = await skill_for_topic(db, q.topic_id)
    if sk is None:
        return None
    m = await db.scalar(select(Mastery).where(Mastery.user_id == user_id,
                                              Mastery.skill_id == sk.id))
    if m is None:
        m = Mastery(user_id=user_id, skill_id=sk.id, mastery_score=0.0, attempt_count=0,
                    correct_count=0, accuracy=0.0, average_time_ms=0.0)
        db.add(m)
    before = m.mastery_score or 0.0
    new = update_mastery(_to_state(m), Evidence(
        correct=correct, difficulty=q.difficulty, at=utcnow(), time_ms=time_ms,
        expected_time_ms=expected_time_ms(q), confidence=confidence))
    for field in ("mastery_score", "attempt_count", "correct_count", "accuracy",
                  "average_time_ms", "confidence", "last_attempt"):
        setattr(m, field, getattr(new, field))
    m.difficulty = {"easy": 0.3, "medium": 0.6, "hard": 0.9}.get(q.difficulty, 0.5)
    return MasteryChange(sk.id, sk.name, round(before, 2), new.mastery_score)


@dataclass
class NodeView:
    id: int
    name: str
    slug: str
    area: str
    parent_id: int | None
    topic_id: int | None
    own: Mastery | None
    rollup: float | None = None
    rollup_attempts: int = 0


async def skill_tree(db: AsyncSession, user_id: int) -> list[NodeView]:
    """All nodes with the user's own mastery and an attempt-weighted rollup over the subtree."""
    skills = (await db.scalars(select(Skill))).all()
    ms = {m.skill_id: m for m in (await db.scalars(
        select(Mastery).where(Mastery.user_id == user_id))).all()}
    nodes = {s.id: NodeView(s.id, s.name, s.slug, s.area, s.parent_id, s.topic_id, ms.get(s.id))
             for s in skills}
    children: dict[int | None, list[int]] = defaultdict(list)
    for n in nodes.values():
        children[n.parent_id].append(n.id)

    def roll(nid: int) -> tuple[float, int]:
        n = nodes[nid]
        total, weight = 0.0, 0
        if n.own and n.own.attempt_count:
            total += n.own.mastery_score * n.own.attempt_count
            weight += n.own.attempt_count
        for c in children.get(nid, []):
            t, w = roll(c)
            total += t
            weight += w
        n.rollup = round(total / weight, 1) if weight else None
        n.rollup_attempts = weight
        return total, weight

    for root in children[None]:
        roll(root)
    return list(nodes.values())


def area_mastery(nodes: list[NodeView]) -> dict[str, tuple[float | None, int]]:
    out: dict[str, tuple[float, int]] = {}
    acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0])
    for n in nodes:
        if n.own and n.own.attempt_count:
            acc[n.area][0] += n.own.mastery_score * n.own.attempt_count
            acc[n.area][1] += n.own.attempt_count
    for area, (t, w) in acc.items():
        out[area] = (round(t / w, 1), int(w))
    return out


async def refresh_profile(db: AsyncSession, user_id: int, active: bool = True) -> None:
    """Recompute competence/behaviour fields on the profile from the skill graph."""
    p = await db.scalar(select(Profile).where(Profile.user_id == user_id))
    if p is None:
        return
    await db.flush()
    nodes = await skill_tree(db, user_id)
    areas = area_mastery(nodes)
    p.dsa_score = areas.get("DSA", (None, 0))[0]
    p.aptitude_score = areas.get("Aptitude", (None, 0))[0]
    csf = [(areas[a][0], areas[a][1]) for a in CSF_AREAS if a in areas]
    p.csf_score = round(sum(v * w for v, w in csf) / sum(w for _, w in csf), 1) if csf else None
    leaf = [n for n in nodes if n.topic_id and n.own and n.own.attempt_count]
    p.topics_completed = sum(1 for n in leaf if n.own.mastery_score >= COMPLETE_THRESHOLD)
    weak = sorted((n for n in leaf if n.own.mastery_score < WEAK_THRESHOLD),
                  key=lambda n: n.own.mastery_score)
    p.weak_topics = [n.name for n in weak[:5]]
    if active:
        today = utcnow().date()
        p.study_streak = next_streak(p.last_active_on, today, p.study_streak or 0)
        p.last_active_on = today
