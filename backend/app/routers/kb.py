"""Knowledge-base management (content managers): upload, list, delete, re-embed."""

from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import require_scopes
from app.models import Company, Document, Topic, User
from app.services import jobs, rag
from app.services.career import UploadError, extract_text

router = APIRouter(prefix="/kb", tags=["knowledge base"])
Kind = Literal["notes", "explanation", "worked_example", "company_prep", "interview_faq",
               "placement_notes"]


class DocIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    kind: Kind = "notes"
    text: str = Field(min_length=20, max_length=200_000)
    topic_id: int | None = None
    company_id: int | None = None


async def _check_refs(db: AsyncSession, topic_id: int | None, company_id: int | None):
    if topic_id and not await db.get(Topic, topic_id):
        raise HTTPException(422, "Unknown topic_id")
    if company_id and not await db.get(Company, company_id):
        raise HTTPException(422, "Unknown company_id")


@router.post("/documents", status_code=201)
async def add_document(body: DocIn, _: User = Depends(require_scopes("content:write")),
                       db: AsyncSession = Depends(get_db)):
    await _check_refs(db, body.topic_id, body.company_id)
    source = await rag.ingest(db, title=body.title, text=body.text, kind=body.kind,
                              topic_id=body.topic_id, company_id=body.company_id)
    await db.commit()
    jobs.enqueue("embed_documents", source=source)
    return {"source": source, "status": "embedding"}


@router.post("/documents/upload", status_code=201)
async def upload_document(file: UploadFile = File(...), title: str = Form(..., max_length=200),
                          kind: Kind = Form("notes"), topic_id: int | None = Form(None),
                          company_id: int | None = Form(None),
                          _: User = Depends(require_scopes("content:write")),
                          db: AsyncSession = Depends(get_db)):
    import tempfile
    from pathlib import Path

    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    name = (file.filename or "").lower()
    if not name.endswith((".txt", ".md", ".pdf")):
        raise HTTPException(422, "Upload .txt, .md or .pdf")
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File too large")
    if name.endswith(".pdf") and not data.startswith(b"%PDF-"):
        raise HTTPException(422, "Not a valid PDF")
    await _check_refs(db, topic_id, company_id)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / ("doc.pdf" if name.endswith(".pdf") else "doc.txt")
        p.write_bytes(data)
        try:
            text = extract_text(p)
        except UploadError as e:
            raise HTTPException(422, str(e)) from None
    if len(text.strip()) < 20:
        raise HTTPException(422, "No extractable text in this file")
    source = await rag.ingest(db, title=title, text=text, kind=kind, topic_id=topic_id,
                              company_id=company_id, source_uri=f"upload://{file.filename}")
    await db.commit()
    jobs.enqueue("embed_documents", source=source)
    return {"source": source, "status": "embedding"}


@router.get("/sources")
async def list_sources(_: User = Depends(require_scopes("content:write")),
                       db: AsyncSession = Depends(get_db)):
    docs = (await db.scalars(select(Document).order_by(Document.id))).all()
    topics = {t.id: t.name for t in (await db.scalars(select(Topic))).all()}
    companies = {c.id: c.name for c in (await db.scalars(select(Company))).all()}
    groups: dict[str, dict] = defaultdict(lambda: {"chunks": 0, "embedded": 0})
    for d in docs:
        key = (d.meta or {}).get("source") or f"doc-{d.id}"
        g = groups[key]
        g.update({"source": key, "title": d.title, "kind": d.kind, "source_uri": d.source_uri,
                  "topic": topics.get(d.topic_id), "company": companies.get(d.company_id),
                  "created_at": d.created_at})
        g["chunks"] += 1
        g["embedded"] += d.embedding is not None
    return sorted(groups.values(), key=lambda g: str(g["created_at"]), reverse=True)


@router.delete("/sources/{source}", status_code=204)
async def delete_source(source: str, _: User = Depends(require_scopes("content:write")),
                        db: AsyncSession = Depends(get_db)):
    docs = (await db.scalars(select(Document))).all()
    hit = [d for d in docs if (d.meta or {}).get("source") == source or f"doc-{d.id}" == source]
    if not hit:
        raise HTTPException(404, "Source not found")
    for d in hit:
        await db.delete(d)
    await db.commit()


@router.post("/reembed")
async def reembed(all_documents: bool = False,
                  _: User = Depends(require_scopes("content:write")),
                  db: AsyncSession = Depends(get_db)):
    """Embed pending chunks (or clear and re-embed everything, e.g. after a model change)."""
    if all_documents:
        await db.execute(update(Document).values(embedding=None))
        await db.commit()
    jobs.enqueue("embed_documents")
    return {"queued": True}


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(default=5, ge=1, le=10)


@router.post("/search")
async def search(body: SearchIn, user: User = Depends(require_scopes("content:write")),
                 db: AsyncSession = Depends(get_db)):
    """Retrieval debugging for content managers (no LLM call)."""
    chunks = await rag.search(db, body.query, k=body.k, user_id=user.id)
    await db.commit()
    return [{"id": c.id, "title": c.title, "score": c.score, "topic": c.topic,
             "company": c.company, "snippet": c.content[:300]} for c in chunks]
