from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_scopes
from app.models import Question, Topic, User
from app.routers.util import unique_slug
from app.schemas import TopicIn, TopicOut, TopicUpdate
from app.services.skill_graph import skill_for_topic

router = APIRouter(prefix="/topics", tags=["topics"])


async def _out(db: AsyncSession, t: Topic) -> TopicOut:
    n = await db.scalar(select(func.count(Question.id)).where(
        Question.topic_id == t.id, Question.status == "published"))
    return TopicOut.model_validate(t).model_copy(update={"question_count": n or 0})


async def _check_parent(db: AsyncSession, parent_id: int | None, self_id: int | None = None):
    if parent_id is None:
        return
    # Walk up to prevent cycles
    cur = parent_id
    seen = set()
    while cur is not None:
        if cur == self_id or cur in seen:
            raise HTTPException(422, "Parent would create a cycle")
        seen.add(cur)
        node = await db.get(Topic, cur)
        if node is None:
            raise HTTPException(422, "Parent topic not found")
        cur = node.parent_id


@router.get("", response_model=list[TopicOut])
async def list_topics(area: str | None = None, _: User = Depends(require_scopes("content:read")),
                      db: AsyncSession = Depends(get_db)):
    counts = (
        select(Question.topic_id, func.count(Question.id).label("n"))
        .where(Question.status == "published").group_by(Question.topic_id).subquery()
    )
    stmt = select(Topic, func.coalesce(counts.c.n, 0)).outerjoin(
        counts, counts.c.topic_id == Topic.id)
    if area:
        stmt = stmt.where(Topic.area == area)
    rows = (await db.execute(stmt.order_by(Topic.area, Topic.name))).all()
    return [TopicOut.model_validate(t).model_copy(update={"question_count": n}) for t, n in rows]


@router.post("", response_model=TopicOut, status_code=201)
async def create_topic(body: TopicIn, _: User = Depends(require_scopes("content:write")),
                       db: AsyncSession = Depends(get_db)):
    await _check_parent(db, body.parent_id)
    t = Topic(**body.model_dump(), slug=await unique_slug(db, Topic, body.name))
    db.add(t)
    await db.flush()
    await skill_for_topic(db, t.id)  # every topic gets its skill-graph node immediately
    await db.commit()
    return await _out(db, t)


@router.patch("/{topic_id}", response_model=TopicOut)
async def update_topic(topic_id: int, body: TopicUpdate,
                       _: User = Depends(require_scopes("content:write")),
                       db: AsyncSession = Depends(get_db)):
    t = await db.get(Topic, topic_id)
    if t is None:
        raise HTTPException(404, "Topic not found")
    data = body.model_dump(exclude_unset=True)
    if "parent_id" in data:
        await _check_parent(db, data["parent_id"], self_id=t.id)
    if "name" in data:
        t.slug = await unique_slug(db, Topic, data["name"], exclude_id=t.id)
    for k, v in data.items():
        setattr(t, k, v)
    await db.commit()
    return await _out(db, t)


@router.delete("/{topic_id}", status_code=204)
async def delete_topic(topic_id: int, _: User = Depends(require_scopes("content:write")),
                       db: AsyncSession = Depends(get_db)):
    t = await db.get(Topic, topic_id)
    if t is None:
        raise HTTPException(404, "Topic not found")
    await db.delete(t)
    await db.commit()
