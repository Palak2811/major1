from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

PATTERN_DISCLAIMER = (
    "Observed historical preparation pattern, not an official specification. "
    "Compiled from past candidate experiences; the company may change its process at any time."
)

QuestionType = Literal[
    "mcq", "multi_select", "numerical", "coding", "output_prediction", "sql", "debugging", "theory"
]
Difficulty = Literal["easy", "medium", "hard"]
Area = Literal["DSA", "DBMS", "OS", "CN", "OOP", "Aptitude", "HR", "General"]
RoleName = Literal["student", "content_manager", "admin"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)

    @field_validator("password")
    @classmethod
    def strong(cls, v: str) -> str:
        if v.isalpha() or v.isdigit():
            raise ValueError("Password must mix letters with digits or symbols")
        return v


class LoginIn(BaseModel):
    # Plain string: login only matches existing accounts, format is enforced at registration
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: str
    scopes: list[str]
    is_active: bool
    has_password: bool
    google_linked: bool
    created_at: datetime

    @classmethod
    def of(cls, u) -> "UserOut":
        return cls(
            id=u.id, email=u.email, full_name=u.full_name, role=u.role.name,
            scopes=u.role.scopes, is_active=u.is_active, has_password=bool(u.password_hash),
            google_linked=bool(u.google_sub), created_at=u.created_at,
        )


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserAdminUpdate(BaseModel):
    role: RoleName | None = None
    is_active: bool | None = None
    full_name: str | None = Field(default=None, max_length=120)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


# ---------- Profile ----------


class ProfileIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    college: str = Field(default="", max_length=200)
    branch: str = Field(default="", max_length=120)
    graduation_year: int | None = Field(default=None, ge=2000, le=2100)
    target_role: str = Field(default="", max_length=120)
    target_company_ids: list[int] = Field(default_factory=list, max_length=10)
    preferred_language: Literal["python", "cpp", "java", "javascript"] = "python"


class ProfileOut(ORM):
    user_id: int
    full_name: str
    email: str
    college: str
    branch: str
    graduation_year: int | None
    target_role: str
    target_company_ids: list[int]
    dsa_score: float | None
    csf_score: float | None
    aptitude_score: float | None
    coding_score: float | None
    study_streak: int
    topics_completed: int
    weak_topics: list[str]
    preferred_language: str
    resume_id: int | None
    completeness: int  # % of identity/intent fields filled


# ---------- Topics ----------


class TopicIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    area: Area
    description: str = Field(default="", max_length=5000)
    parent_id: int | None = None


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    area: Area | None = None
    description: str | None = Field(default=None, max_length=5000)
    parent_id: int | None = None


class TopicOut(ORM):
    id: int
    name: str
    slug: str
    area: str
    description: str
    parent_id: int | None
    question_count: int = 0


# ---------- Companies ----------


class SkillWeights(BaseModel):
    dsa: float = Field(ge=0, le=100)
    oop: float = Field(ge=0, le=100)
    dbms: float = Field(ge=0, le=100)
    os: float = Field(ge=0, le=100)
    aptitude: float = Field(ge=0, le=100)
    hr: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def sums_to_100(self):
        total = sum(self.model_dump().values())
        if abs(total - 100) > 0.01:
            raise ValueError(f"Skill weights must sum to 100 (got {total:g})")
        return self


class OAPattern(BaseModel):
    coding_questions: int = Field(ge=0, le=20)
    mcqs: int = Field(ge=0, le=200)
    duration_minutes: int = Field(ge=5, le=600)
    difficulty: Difficulty
    frequent_topics: list[str] = Field(default_factory=list, max_length=30)


class ReadinessWeights(BaseModel):
    """Equation 3.1 weights; used by Phase 3. Must sum to 1."""

    dsa: float = Field(ge=0, le=1)
    csf: float = Field(ge=0, le=1)
    coding: float = Field(ge=0, le=1)
    aptitude: float = Field(ge=0, le=1)
    interview: float = Field(ge=0, le=1)
    consistency: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def sums_to_1(self):
        total = sum(self.model_dump().values())
        if abs(total - 1) > 1e-6:
            raise ValueError(f"Readiness weights must sum to 1 (got {total:g})")
        return self


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=5000)
    skill_weights: SkillWeights
    oa_pattern: OAPattern
    readiness_weights: ReadinessWeights | None = None


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    skill_weights: SkillWeights | None = None
    oa_pattern: OAPattern | None = None
    readiness_weights: ReadinessWeights | None = None


class CompanyOut(ORM):
    id: int
    name: str
    slug: str
    description: str
    skill_weights: SkillWeights
    oa_pattern: OAPattern
    readiness_weights: ReadinessWeights | None
    pattern_disclaimer: str = PATTERN_DISCLAIMER
    question_count: int = 0


class CompanyRef(ORM):
    id: int
    name: str
    slug: str


# ---------- Questions ----------


class Option(BaseModel):
    id: str = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1, max_length=2000)


class QuestionBase(BaseModel):
    type: QuestionType
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    difficulty: Difficulty
    topic_id: int | None = None
    company_ids: list[int] = Field(default_factory=list, max_length=20)
    options: list[Option] = Field(default_factory=list, max_length=10)
    answer: dict = Field(default_factory=dict)
    explanation: str = Field(default="", max_length=20000)
    meta: dict = Field(default_factory=dict)
    # review/rejected are only ever set by the AI generation pipeline and the review queue
    status: Literal["draft", "published", "archived", "review", "rejected"] = "draft"

    @model_validator(mode="after")
    def validate_shape(self):
        validate_question_shape(self.type, self.options, self.answer, self.meta)
        return self


def validate_question_shape(qtype: str, options: list[Option], answer: dict, meta: dict) -> None:
    """Per-type contract. Answers for every type must be machine-checkable where possible."""
    ids = [o.id for o in options]
    if len(set(ids)) != len(ids):
        raise ValueError("Option ids must be unique")

    if qtype in ("mcq", "multi_select"):
        if len(options) < 2:
            raise ValueError(f"{qtype} needs at least 2 options")
        correct = answer.get("correct")
        if not isinstance(correct, list) or not correct:
            raise ValueError("answer.correct must be a non-empty list of option ids")
        if any(c not in ids for c in correct):
            raise ValueError("answer.correct references unknown option id")
        if qtype == "mcq" and len(correct) != 1:
            raise ValueError("mcq must have exactly one correct option")
    elif options:
        raise ValueError(f"{qtype} questions must not have options")

    if qtype == "numerical":
        if not isinstance(answer.get("value"), int | float):
            raise ValueError("numerical answer.value must be a number")
        tol = answer.get("tolerance", 0)
        if not isinstance(tol, int | float) or tol < 0:
            raise ValueError("answer.tolerance must be a non-negative number")
    elif qtype == "output_prediction":
        if not isinstance(answer.get("expected_output"), str):
            raise ValueError("output_prediction needs answer.expected_output (string)")
        if not meta.get("code"):
            raise ValueError("output_prediction needs meta.code")
    elif qtype == "coding":
        for key in ("constraints", "input_format", "output_format"):
            if not meta.get(key):
                raise ValueError(f"coding question needs meta.{key}")
        samples = meta.get("samples")
        if not isinstance(samples, list) or not samples:
            raise ValueError("coding question needs at least one meta.samples entry")
        for s in samples:
            if not isinstance(s, dict) or "input" not in s or "output" not in s:
                raise ValueError("each sample needs input and output")
    elif qtype == "sql":
        if not meta.get("schema_sql"):
            raise ValueError("sql question needs meta.schema_sql")
        if not isinstance(answer.get("reference_query"), str):
            raise ValueError("sql question needs answer.reference_query")
    elif qtype == "debugging":
        if not meta.get("code"):
            raise ValueError("debugging question needs meta.code (the buggy snippet)")
    elif qtype == "theory":
        kp = answer.get("key_points", [])
        if not isinstance(kp, list):
            raise ValueError("theory answer.key_points must be a list")


class QuestionIn(QuestionBase):
    pass


class QuestionUpdate(BaseModel):
    """Partial update; the merged result is re-validated in the router."""

    type: QuestionType | None = None
    title: str | None = Field(default=None, min_length=3, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=20000)
    difficulty: Difficulty | None = None
    topic_id: int | None = None
    company_ids: list[int] | None = None
    options: list[Option] | None = None
    answer: dict | None = None
    explanation: str | None = Field(default=None, max_length=20000)
    meta: dict | None = None
    status: Literal["draft", "published", "archived", "review", "rejected"] | None = None


class TopicRef(ORM):
    id: int
    name: str
    slug: str
    area: str


class QuestionOut(ORM):
    id: int
    type: str
    title: str
    body: str
    difficulty: str
    topic: TopicRef | None
    companies: list[CompanyRef]
    options: list[Option]
    meta: dict
    status: str
    source: str
    created_at: datetime
    updated_at: datetime
    # Only returned to content roles; students get answers after attempting (Phase 2)
    answer: dict | None = None
    explanation: str | None = None


class StatsOut(BaseModel):
    users: int
    students: int
    topics: int
    questions_published: int
    questions_draft: int
    companies: int
