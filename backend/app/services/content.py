"""Study-mode teaching content behind a provider interface.

Phase 2 serves curated documents from the `documents` table (kind = explanation |
worked_example). Phase 4 adds a RAG provider implementing the same interface, so the
Study Mode loop does not change.
"""

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, Topic


@dataclass
class Source:
    document_id: int
    title: str


@dataclass
class TeachingBlock:
    kind: str  # explanation | worked_example
    title: str
    body: str
    grounded: bool  # True only when backed by stored documents
    provider: str
    sources: list[Source] = field(default_factory=list)


class ContentProvider(Protocol):
    async def teach(self, db: AsyncSession, topic: Topic, kind: str) -> TeachingBlock | None: ...


class CuratedContentProvider:
    name = "curated"

    async def teach(self, db: AsyncSession, topic: Topic, kind: str) -> TeachingBlock | None:
        # Walk up the topic hierarchy until curated content is found.
        cur: Topic | None = topic
        while cur is not None:
            docs = (await db.scalars(
                select(Document).where(Document.topic_id == cur.id, Document.kind == kind)
                .order_by(Document.chunk_index))).all()
            if docs:
                return TeachingBlock(
                    kind=kind, title=docs[0].title, body="\n\n".join(d.content for d in docs),
                    grounded=True, provider=self.name,
                    sources=[Source(d.id, d.title) for d in docs])
            cur = await db.get(Topic, cur.parent_id) if cur.parent_id else None
        return None


def get_provider() -> ContentProvider:
    return CuratedContentProvider()
