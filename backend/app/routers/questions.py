from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_scopes
from app.models import Company, Question, Topic, User, question_companies
from app.schemas import Page, QuestionIn, QuestionOut, QuestionUpdate

router = APIRouter(prefix="/questions", tags=["questions"])


def _can_write(user: User) -> bool:
    return "content:write" in (user.role.scopes or [])


def _out(q: Question, reveal: bool) -> QuestionOut:
    # from_attributes would copy answer/explanation off the ORM row; strip them explicitly
    # for students (coding answers also hold the hidden judge tests).
    out = QuestionOut.model_validate(q)
    if reveal:
        return out
    return out.model_copy(update={"answer": None, "explanation": None})


async def _companies(db: AsyncSession, ids: list[int]) -> list[Company]:
    ids = list(dict.fromkeys(ids))
    if not ids:
        return []
    rows = (await db.scalars(select(Company).where(Company.id.in_(ids)))).all()
    if len(rows) != len(ids):
        raise HTTPException(422, "Unknown company id in company_ids")
    return list(rows)


async def _check_topic(db: AsyncSession, topic_id: int | None):
    if topic_id is not None and await db.get(Topic, topic_id) is None:
        raise HTTPException(422, "Unknown topic_id")


@router.get("", response_model=Page[QuestionOut])
async def list_questions(
    type: str | None = None,
    difficulty: str | None = None,
    topic_id: int | None = None,
    company_id: int | None = None,
    status: str | None = None,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_scopes("content:read")),
    db: AsyncSession = Depends(get_db),
):
    writer = _can_write(user)
    stmt = select(Question)
    # Students only ever see published questions, regardless of the filter they send.
    if not writer:
        stmt = stmt.where(Question.status == "published")
    elif status:
        stmt = stmt.where(Question.status == status)
    if type:
        stmt = stmt.where(Question.type == type)
    if difficulty:
        stmt = stmt.where(Question.difficulty == difficulty)
    if topic_id:
        stmt = stmt.where(Question.topic_id == topic_id)
    if company_id:
        stmt = stmt.where(Question.id.in_(
            select(question_companies.c.question_id).where(
                question_companies.c.company_id == company_id)))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Question.title).like(like),
                              func.lower(Question.body).like(like)))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.scalars(
        stmt.order_by(Question.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).unique().all()
    return Page(items=[_out(r, writer) for r in rows], total=total or 0, page=page,
                page_size=page_size)


@router.get("/{question_id}", response_model=QuestionOut)
async def get_question(question_id: int, user: User = Depends(require_scopes("content:read")),
                       db: AsyncSession = Depends(get_db)):
    q = await db.get(Question, question_id)
    writer = _can_write(user)
    if q is None or (not writer and q.status != "published"):
        raise HTTPException(404, "Question not found")
    return _out(q, writer)


@router.post("", response_model=QuestionOut, status_code=201)
async def create_question(body: QuestionIn, user: User = Depends(require_scopes("content:write")),
                          db: AsyncSession = Depends(get_db)):
    if body.status in ("review", "rejected"):
        raise HTTPException(422, "Manual questions can't enter the AI review queue")
    await _check_topic(db, body.topic_id)
    data = body.model_dump(exclude={"company_ids"})
    q = Question(**data, source="manual", created_by=user.id,
                 companies=await _companies(db, body.company_ids))
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return _out(q, True)


@router.patch("/{question_id}", response_model=QuestionOut)
async def update_question(question_id: int, body: QuestionUpdate,
                          _: User = Depends(require_scopes("content:write")),
                          db: AsyncSession = Depends(get_db)):
    q = await db.get(Question, question_id)
    if q is None:
        raise HTTPException(404, "Question not found")
    patch = body.model_dump(exclude_unset=True)
    if patch.get("status") in ("review", "rejected") and patch["status"] != q.status:
        raise HTTPException(409, "review/rejected statuses are managed by the AI review queue")
    if q.source == "ai" and q.status != "published" and patch.get("status") == "published":
        raise HTTPException(409, "AI-generated questions are published only through the "
                                 "review queue")
    merged = {
        "type": q.type, "title": q.title, "body": q.body, "difficulty": q.difficulty,
        "topic_id": q.topic_id, "company_ids": [c.id for c in q.companies],
        "options": q.options, "answer": q.answer, "explanation": q.explanation,
        "meta": q.meta, "status": q.status, **patch,
    }
    try:
        valid = QuestionIn.model_validate(merged)  # re-run the full per-type contract
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False)) from None
    await _check_topic(db, valid.topic_id)
    for k, v in valid.model_dump(exclude={"company_ids"}).items():
        setattr(q, k, v)
    q.companies = await _companies(db, valid.company_ids)
    await db.commit()
    await db.refresh(q)
    return _out(q, True)


@router.delete("/{question_id}", status_code=204)
async def delete_question(question_id: int, _: User = Depends(require_scopes("content:write")),
                          db: AsyncSession = Depends(get_db)):
    q = await db.get(Question, question_id)
    if q is None:
        raise HTTPException(404, "Question not found")
    await db.delete(q)
    await db.commit()
