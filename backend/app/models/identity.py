from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utcnow


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped[Role] = relationship(lazy="joined")
    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", lazy="selectin", cascade="all, delete-orphan", uselist=False
    )


class UserSession(Base):
    """One row per issued refresh token. Rotation chains share a family_id."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[str] = mapped_column(String(64), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[int | None] = mapped_column(Integer)
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    # identity / academic
    college: Mapped[str] = mapped_column(String(200), default="")
    branch: Mapped[str] = mapped_column(String(120), default="")
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    # intent
    target_role: Mapped[str] = mapped_column(String(120), default="")
    target_company_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    # competence (populated by later phases; null = not yet measured)
    dsa_score: Mapped[float | None] = mapped_column(Float)
    csf_score: Mapped[float | None] = mapped_column(Float)
    aptitude_score: Mapped[float | None] = mapped_column(Float)
    coding_score: Mapped[float | None] = mapped_column(Float)
    # behavioural
    study_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_on: Mapped[date | None] = mapped_column(Date)
    topics_completed: Mapped[int] = mapped_column(Integer, default=0)
    weak_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_language: Mapped[str] = mapped_column(String(32), default="python")
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"))

    user: Mapped[User] = relationship(back_populates="profile")
