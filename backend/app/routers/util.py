import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "item"


async def unique_slug(db: AsyncSession, model, name: str, exclude_id: int | None = None) -> str:
    base = slugify(name)
    slug, n = base, 2
    while True:
        q = select(model.id).where(model.slug == slug)
        if exclude_id is not None:
            q = q.where(model.id != exclude_id)
        if not await db.scalar(q):
            return slug
        slug = f"{base}-{n}"
        n += 1
