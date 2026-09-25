"""Resume & job-description analysis endpoints."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import require_scopes
from app.models import JobDescription, Profile, Resume, User
from app.services import jobs
from app.services.career import UploadError, compare, topics_by_slug, validate_upload

router = APIRouter(prefix="/career", tags=["career"])


def _resume_view(r: Resume) -> dict:
    return {"id": r.id, "filename": r.filename, "status": r.status, "parsed": r.parsed,
            "created_at": r.created_at}


def _jd_view(j: JobDescription) -> dict:
    return {"id": j.id, "title": j.title, "company_name": j.company_name,
            "raw_text": j.raw_text, "parsed": j.parsed,
            "status": (j.parsed or {}).get("status", "pending"), "created_at": j.created_at}


@router.post("/resume", status_code=202)
async def upload_resume(file: UploadFile = File(...), user: User = Depends(require_scopes("me")),
                        db: AsyncSession = Depends(get_db)):
    s = get_settings()
    data = await file.read(s.max_upload_mb * 1024 * 1024 + 1)
    try:
        ext = validate_upload(file.filename or "", file.content_type, data, s.max_upload_mb)
    except UploadError as e:
        raise HTTPException(422, str(e)) from None
    folder = Path(s.uploads_dir) / "resumes" / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{ext}"  # never trust the client filename on disk
    path.write_bytes(data)
    r = Resume(user_id=user.id, filename=Path(file.filename or "resume").name[:200],
               content_type=file.content_type or "", storage_path=str(path), status="pending")
    db.add(r)
    await db.flush()
    p = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if p:
        p.resume_id = r.id
    await db.commit()
    jobs.enqueue("parse_resume", resume_id=r.id)
    return _resume_view(r)


@router.get("/resume")
async def my_resumes(user: User = Depends(require_scopes("me")),
                     db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Resume).where(Resume.user_id == user.id)
                             .order_by(Resume.created_at.desc()))).all()
    return [_resume_view(r) for r in rows]


@router.get("/resume/{resume_id}")
async def get_resume(resume_id: int, user: User = Depends(require_scopes("me")),
                     db: AsyncSession = Depends(get_db)):
    r = await db.get(Resume, resume_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(404, "Resume not found")
    return _resume_view(r)


class JDIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    company_name: str = Field(default="", max_length=120)
    raw_text: str = Field(min_length=50, max_length=20_000)


@router.post("/jd", status_code=202)
async def add_jd(body: JDIn, user: User = Depends(require_scopes("me")),
                 db: AsyncSession = Depends(get_db)):
    j = JobDescription(user_id=user.id, title=body.title, company_name=body.company_name,
                       raw_text=body.raw_text, parsed={"status": "pending"})
    db.add(j)
    await db.commit()
    jobs.enqueue("parse_jd", jd_id=j.id)
    return _jd_view(j)


@router.get("/jd")
async def my_jds(user: User = Depends(require_scopes("me")), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(JobDescription).where(JobDescription.user_id == user.id)
                             .order_by(JobDescription.created_at.desc()))).all()
    return [_jd_view(j) for j in rows]


@router.get("/jd/{jd_id}")
async def get_jd(jd_id: int, user: User = Depends(require_scopes("me")),
                 db: AsyncSession = Depends(get_db)):
    j = await db.get(JobDescription, jd_id)
    if j is None or j.user_id != user.id:
        raise HTTPException(404, "Job description not found")
    return _jd_view(j)


@router.get("/gap")
async def skill_gap(resume_id: int, jd_id: int, user: User = Depends(require_scopes("me")),
                    db: AsyncSession = Depends(get_db)):
    r = await db.get(Resume, resume_id)
    j = await db.get(JobDescription, jd_id)
    if r is None or r.user_id != user.id or j is None or j.user_id != user.id:
        raise HTTPException(404, "Resume or job description not found")
    if r.status != "parsed" or (j.parsed or {}).get("status") != "parsed":
        raise HTTPException(409, "Still parsing — try again in a few seconds")
    return {"resume_id": r.id, "jd_id": j.id, "jd_title": j.title,
            **compare(r.parsed, j.parsed, await topics_by_slug(db))}
