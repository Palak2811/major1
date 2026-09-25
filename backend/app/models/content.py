from sqlalchemy import JSON, Column, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Embedding, TimestampMixin

question_companies = Table(
    "question_companies",
    Base.metadata,
    Column("question_id", ForeignKey("questions.id", ondelete="CASCADE"),
           primary_key=True),
    Column("company_id", ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True),
)


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    area: Mapped[str] = mapped_column(String(32), index=True)  # DSA, DBMS, OS, CN, OOP, ...
    description: Mapped[str] = mapped_column(Text, default="")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))


class Skill(Base):
    """Node of the hierarchical skill graph (logic arrives in Phase 2)."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True)
    area: Mapped[str] = mapped_column(String(32))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    difficulty: Mapped[float] = mapped_column(Float, default=0.5)


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(16), index=True)
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), index=True
    )
    options: Mapped[list[dict]] = mapped_column(JSON, default=list)
    answer: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual | ai
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    topic: Mapped["Topic | None"] = relationship(lazy="joined")
    companies: Mapped[list["Company"]] = relationship(  # noqa: F821
        secondary=question_companies, lazy="selectin"
    )


class TestQuestion(Base):
    __tablename__ = "test_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(String(64), default="General")
    position: Mapped[int] = mapped_column(Integer, default=0)
    marks: Mapped[float] = mapped_column(Float, default=1.0)
    negative_marks: Mapped[float] = mapped_column(Float, default=0.0)


class Document(Base, TimestampMixin):
    """Knowledge-base chunk with pgvector embedding (HNSW index created in migration)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32), default="notes")
    source_uri: Mapped[str] = mapped_column(String(500), default="")
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    embedding: Mapped[list[float] | None] = mapped_column(Embedding())
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
