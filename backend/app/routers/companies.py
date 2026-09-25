from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_scopes
from app.models import Company, User, question_companies
from app.routers.util import unique_slug
from app.schemas import CompanyIn, CompanyOut, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


async def _out(db: AsyncSession, c: Company) -> CompanyOut:
    n = await db.scalar(select(func.count()).where(question_companies.c.company_id == c.id))
    return CompanyOut.model_validate(c).model_copy(update={"question_count": n or 0})


async def _get(db: AsyncSession, key: str) -> Company:
    stmt = select(Company).where(
        Company.id == int(key) if key.isdigit() else Company.slug == key)
    c = await db.scalar(stmt)
    if c is None:
        raise HTTPException(404, "Company not found")
    return c


@router.get("", response_model=list[CompanyOut])
async def list_companies(_: User = Depends(require_scopes("content:read")),
                         db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Company).order_by(Company.name))).all()
    return [await _out(db, c) for c in rows]


@router.get("/{key}", response_model=CompanyOut)
async def get_company(key: str, _: User = Depends(require_scopes("content:read")),
                      db: AsyncSession = Depends(get_db)):
    return await _out(db, await _get(db, key))


@router.post("", response_model=CompanyOut, status_code=201)
async def create_company(body: CompanyIn, _: User = Depends(require_scopes("content:write")),
                         db: AsyncSession = Depends(get_db)):
    if await db.scalar(select(Company.id).where(func.lower(Company.name) == body.name.lower())):
        raise HTTPException(409, "Company already exists")
    c = Company(**body.model_dump(), slug=await unique_slug(db, Company, body.name))
    db.add(c)
    await db.commit()
    return await _out(db, c)


@router.patch("/{key}", response_model=CompanyOut)
async def update_company(key: str, body: CompanyUpdate,
                         _: User = Depends(require_scopes("content:write")),
                         db: AsyncSession = Depends(get_db)):
    c = await _get(db, key)
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        c.slug = await unique_slug(db, Company, data["name"], exclude_id=c.id)
    for k, v in data.items():
        setattr(c, k, v)
    await db.commit()
    return await _out(db, c)


@router.delete("/{key}", status_code=204)
async def delete_company(key: str, _: User = Depends(require_scopes("content:write")),
                         db: AsyncSession = Depends(get_db)):
    await db.delete(await _get(db, key))
    await db.commit()
