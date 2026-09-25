"""Knowledge base ingestion + retrieval (RAG).

Documents are chunked, embedded (Gemini, 768-d) and stored in `documents.embedding`.
On Postgres, search uses pgvector cosine distance (HNSW index from migration 0001);
on SQLite (local dev/tests) the same ranking is computed in Python.
"""

import math
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Document, Topic
from app.services import jobs, llm

CHUNK_CHARS = 900
OVERLAP_CHARS = 150
MIN_SCORE_REAL = 0.55  # cosine similarity floor for Gemini embeddings
MIN_SCORE_MOCK = 0.05  # hashing embeddings are sparse; lower floor


@dataclass
class Chunk:
    id: int
    title: str
    content: str
    kind: str
    topic: str | None
    company: str | None
    source_uri: str
    score: float

    @property
    def ref(self) -> str:
        return f"S{self.id}"


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Paragraph-aware chunking with character overlap between consecutive chunks."""
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        while len(p) > size:  # hard-split giant paragraphs on sentence boundaries
            cut = p.rfind(". ", 0, size)
            cut = cut + 1 if cut > size // 2 else size
            pieces, p = p[:cut].strip(), p[cut:].strip()
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(pieces)
        if len(cur) + len(p) + 2 <= size:
            cur = f"{cur}\n\n{p}" if cur else p
        else:
            if cur:
                chunks.append(cur)
            tail = cur[-overlap:] if cur and overlap else ""
            cur = f"{tail}\n\n{p}".strip() if tail else p
    if cur:
        chunks.append(cur)
    return chunks


async def ingest(db: AsyncSession, *, title: str, text: str, kind: str = "notes",
                 topic_id: int | None = None, company_id: int | None = None,
                 source_uri: str = "", embed_now: bool = False) -> str:
    """Store chunks (unembedded) and queue embedding. Returns the source id."""
    source = uuid.uuid4().hex
    for i, c in enumerate(chunk_text(text)):
        db.add(Document(title=title, kind=kind, content=c, chunk_index=i, topic_id=topic_id,
                        company_id=company_id, source_uri=source_uri or f"upload://{source}",
                        meta={"source": source}))
    await db.flush()
    if embed_now:
        await embed_pending(db)
    return source


async def embed_pending(db: AsyncSession, limit: int = 500, source: str | None = None) -> int:
    rows = list((await db.scalars(select(Document).where(Document.embedding.is_(None))
                                  .limit(limit))).all())
    if source:
        rows = [r for r in rows if (r.meta or {}).get("source") == source]
    if not rows:
        return 0
    vecs = await llm.embed(db, [f"{r.title}\n{r.content}" for r in rows])
    for r, v in zip(rows, vecs, strict=True):
        r.embedding = v
    await db.flush()
    return len(rows)


@jobs.job("embed_documents")
async def embed_documents_job(source: str | None = None) -> None:
    async with jobs.session_factory() as db:
        await embed_pending(db, source=source)
        await db.commit()


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


async def search(db: AsyncSession, query: str, *, k: int = 5, topic_ids: list[int] | None = None,
                 company_id: int | None = None, user_id: int | None = None) -> list[Chunk]:
    """Top-k chunks by cosine similarity, preferring the given topics/company when present."""
    [qv] = await llm.embed(db, [query], task="RETRIEVAL_QUERY", user_id=user_id)
    base = select(Document).where(Document.embedding.is_not(None))
    if db.bind.dialect.name == "postgresql":
        dist = Document.embedding.cosine_distance(qv)
        rows = (await db.execute(base.add_columns(dist.label("d")).order_by(dist)
                                 .limit(k * 4))).all()
        scored = [(doc, 1 - float(d)) for doc, d in rows]
    else:
        docs = [d for d in (await db.scalars(base)).all() if d.embedding]
        scored = sorted(((d, _cos(qv, d.embedding)) for d in docs), key=lambda x: -x[1])[:k * 4]

    def boost(doc: Document, s: float) -> float:
        b = 0.0
        if topic_ids and doc.topic_id in topic_ids:
            b += 0.05
        if company_id and doc.company_id == company_id:
            b += 0.05
        return s + b

    ranked = sorted(scored, key=lambda x: -boost(*x))[:k]
    floor = MIN_SCORE_MOCK if llm.is_mock() else MIN_SCORE_REAL
    topics = {t.id: t.name for t in (await db.scalars(select(Topic))).all()}
    companies = {c.id: c.name for c in (await db.scalars(select(Company))).all()}
    return [Chunk(d.id, d.title, d.content, d.kind, topics.get(d.topic_id),
                  companies.get(d.company_id), d.source_uri, round(s, 4))
            for d, s in ranked if s >= floor]
