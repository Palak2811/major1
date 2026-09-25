from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_scopes
from app.models import Company, Profile, Question, Role, Topic, User
from app.schemas import Page, ProfileIn, ProfileOut, StatsOut, UserAdminUpdate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


def _profile_out(user: User, p: Profile) -> ProfileOut:
    fields = [user.full_name, p.college, p.branch, p.graduation_year, p.target_role,
              p.target_company_ids]
    completeness = round(100 * sum(1 for f in fields if f) / len(fields))
    return ProfileOut(
        user_id=user.id, full_name=user.full_name, email=user.email, college=p.college,
        branch=p.branch, graduation_year=p.graduation_year, target_role=p.target_role,
        target_company_ids=p.target_company_ids or [], dsa_score=p.dsa_score,
        csf_score=p.csf_score, aptitude_score=p.aptitude_score, coding_score=p.coding_score,
        study_streak=p.study_streak, topics_completed=p.topics_completed,
        weak_topics=p.weak_topics or [], preferred_language=p.preferred_language,
        resume_id=p.resume_id, completeness=completeness,
    )


async def _ensure_profile(db: AsyncSession, user: User) -> Profile:
    if user.profile is None:
        user.profile = Profile()
        await db.flush()
    return user.profile


@router.get("/me/profile", response_model=ProfileOut)
async def get_my_profile(user: User = Depends(require_scopes("me")),
                         db: AsyncSession = Depends(get_db)):
    p = await _ensure_profile(db, user)
    await db.commit()
    return _profile_out(user, p)


@router.put("/me/profile", response_model=ProfileOut)
async def update_my_profile(body: ProfileIn, user: User = Depends(require_scopes("me")),
                            db: AsyncSession = Depends(get_db)):
    p = await _ensure_profile(db, user)
    ids = list(dict.fromkeys(body.target_company_ids))
    if ids:
        found = set((await db.scalars(select(Company.id).where(Company.id.in_(ids)))).all())
        if missing := [i for i in ids if i not in found]:
            raise HTTPException(422, f"Unknown company id(s): {missing}")
    if body.full_name is not None and body.full_name.strip():
        user.full_name = body.full_name.strip()
    for field in ("college", "branch", "graduation_year", "target_role", "preferred_language"):
        setattr(p, field, getattr(body, field))
    p.target_company_ids = ids
    await db.commit()
    return _profile_out(user, p)


# ---------------- Admin ----------------


@router.get("", response_model=Page[UserOut])
async def list_users(
    q: str | None = Query(default=None, max_length=100),
    role: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: User = Depends(require_scopes("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).join(Role)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like),
                              func.lower(User.full_name).like(like)))
    if role:
        stmt = stmt.where(Role.name == role)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await db.scalars(
        stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).unique().all()
    return Page(items=[UserOut.of(u) for u in rows], total=total or 0, page=page,
                page_size=page_size)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: int, body: UserAdminUpdate,
                      admin: User = Depends(require_scopes("users:manage")),
                      db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and (body.role not in (None, "admin") or body.is_active is False):
        raise HTTPException(400, "You cannot demote or deactivate your own account")
    if body.role is not None:
        role = await db.scalar(select(Role).where(Role.name == body.role))
        user.role = role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.full_name is not None:
        user.full_name = body.full_name
    await db.commit()
    await db.refresh(user)
    return UserOut.of(user)


@router.get("/stats", response_model=StatsOut, tags=["admin"])
async def stats(_: User = Depends(require_scopes("admin:panel")),
                db: AsyncSession = Depends(get_db)):
    count = lambda stmt: db.scalar(select(func.count()).select_from(stmt.subquery()))  # noqa: E731
    return StatsOut(
        users=await count(select(User.id)),
        students=await count(select(User.id).join(Role).where(Role.name == "student")),
        topics=await count(select(Topic.id)),
        questions_published=await count(select(Question.id).where(Question.status == "published")),
        questions_draft=await count(select(Question.id).where(Question.status == "draft")),
        companies=await count(select(Company.id)),
    )
