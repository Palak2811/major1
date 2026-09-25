"""Resume & job-description analysis.

Parsing (unstructured text → structured fields) uses the LLM asynchronously.
The comparison and the job-readiness percentage are DETERMINISTIC (normalised skill matching),
so the same resume + JD always give the same score.
"""

import io
import re
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobDescription, Resume, Topic
from app.services import jobs, llm
from app.services.guardrails import SYSTEM_BASE, Checks, clean_input, wrap_student

# ---------------- parsing contracts ----------------


class Project(BaseModel):
    name: str = Field(max_length=200)
    description: str = Field(max_length=800)
    technologies: list[str] = Field(max_length=15)


class Experience(BaseModel):
    role: str = Field(max_length=200)
    organization: str = Field(max_length=200)
    duration: str = Field(max_length=100)
    highlights: list[str] = Field(max_length=8)


class Education(BaseModel):
    degree: str = Field(max_length=200)
    institution: str = Field(max_length=200)
    year: str = Field(max_length=40)


class ResumeParsed(BaseModel):
    skills: list[str] = Field(max_length=60)
    projects: list[Project] = Field(max_length=12)
    experience: list[Experience] = Field(max_length=12)
    education: list[Education] = Field(max_length=6)
    achievements: list[str] = Field(max_length=15)


class JDParsed(BaseModel):
    required_skills: list[str] = Field(max_length=40)
    technologies: list[str] = Field(max_length=40)
    responsibilities: list[str] = Field(max_length=20)
    nice_to_have: list[str] = Field(max_length=20)


# ---------------- text extraction & upload validation ----------------

ALLOWED = {".pdf": "application/pdf", ".txt": "text/plain"}


class UploadError(ValueError):
    pass


def validate_upload(filename: str, content_type: str | None, data: bytes, max_mb: int) -> str:
    """Type (extension + declared type + magic bytes), size and content checks."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise UploadError("Only .pdf or .txt resumes are accepted")
    if len(data) == 0:
        raise UploadError("The file is empty")
    if len(data) > max_mb * 1024 * 1024:
        raise UploadError(f"File too large (max {max_mb} MB)")
    if content_type and content_type not in (ALLOWED[ext], "application/octet-stream"):
        raise UploadError("File type doesn't match its extension")
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise UploadError("Not a valid PDF file")
    if ext == ".txt":
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise UploadError("Text resumes must be UTF-8") from None
    return ext


def extract_text(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UploadError("Encrypted PDFs are not supported")
        return "\n".join((p.extract_text() or "") for p in reader.pages[:10])
    return data.decode("utf-8", errors="replace")


# ---------------- async parse jobs ----------------


@jobs.job("parse_resume")
async def parse_resume(resume_id: int) -> None:
    async with jobs.session_factory() as db:
        r = await db.get(Resume, resume_id)
        if r is None:
            return
        try:
            text = extract_text(Path(r.storage_path))
            checks = Checks()
            text = clean_input(text[:15000], checks, max_chars=15000, field_name="resume")
            if len(text) < 30:
                raise UploadError("Couldn't read any text from this resume (is it a scan?)")
            data, info = await llm.structured(
                db, user_id=r.user_id, task="parse_resume", system=SYSTEM_BASE,
                prompt="TASK: Extract the resume into the schema. Copy facts only; do not invent. "
                       "Skills are short canonical names (e.g. 'Python', 'SQL', 'React').\n"
                       + wrap_student(text), output=ResumeParsed, count_rate=False,
                meta={"resume_id": r.id})
            r.parsed = {**data.model_dump(), "_model": info["model"], "_mock": info["mock"],
                        "_input_flags": checks.input_flags}
            r.status = "parsed"
        except (UploadError, llm.AIError) as e:
            r.status = "failed"
            r.parsed = {"error": str(e)}
        await db.commit()


@jobs.job("parse_jd")
async def parse_jd(jd_id: int) -> None:
    async with jobs.session_factory() as db:
        jd = await db.get(JobDescription, jd_id)
        if jd is None:
            return
        try:
            data, info = await llm.structured(
                db, user_id=jd.user_id, task="parse_jd", system=SYSTEM_BASE,
                prompt="TASK: Extract the job description into the schema. Skills and "
                       "technologies are short canonical names.\n" + wrap_student(jd.raw_text),
                output=JDParsed, count_rate=False, meta={"jd_id": jd.id})
            jd.parsed = {**data.model_dump(), "_model": info["model"], "_mock": info["mock"],
                         "status": "parsed"}
        except llm.AIError as e:
            jd.parsed = {"status": "failed", "error": str(e)}
        await db.commit()


# ---------------- deterministic comparison ----------------

ALIASES = {
    "js": "javascript", "node": "node.js", "nodejs": "node.js", "reactjs": "react",
    "react.js": "react", "ts": "typescript", "c plus plus": "c++", "cpp": "c++",
    "postgres": "postgresql", "psql": "postgresql", "mongo": "mongodb", "k8s": "kubernetes",
    "ml": "machine learning", "dl": "deep learning", "dsa": "data structures and algorithms",
    "data structures": "data structures and algorithms", "algorithms":
    "data structures and algorithms", "oops": "oop", "object oriented programming": "oop",
    "object-oriented programming": "oop", "rest": "rest api", "restful apis": "rest api",
    "rest apis": "rest api", "dbms": "databases", "database": "databases", "os":
    "operating systems", "cn": "computer networks", "networking": "computer networks",
    "golang": "go", "aws cloud": "aws", "amazon web services": "aws", "gcp": "google cloud",
}

# missing skill → platform topic slug to study
SKILL_TOPIC = {
    "data structures and algorithms": "arrays", "sql": "sql", "databases": "normalization",
    "postgresql": "sql", "mysql": "sql", "operating systems": "processes-threads",
    "computer networks": "osi-tcp-ip", "oop": "principles", "java": "principles",
    "dynamic programming": "dynamic-programming", "graphs": "graphs", "aptitude": "quantitative",
}


def norm_skill(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip().lower().replace("_", " "))
    s = re.sub(r"[()]", "", s)
    s = s.rstrip(".")
    return ALIASES.get(s, s)


def resume_skill_set(parsed: dict) -> set[str]:
    out = {norm_skill(s) for s in parsed.get("skills", [])}
    for p in parsed.get("projects", []):
        out |= {norm_skill(t) for t in p.get("technologies", [])}
    return {s for s in out if s}


def _matches(req: str, have: set[str]) -> bool:
    if req in have:
        return True
    pattern = re.compile(rf"(^|\W){re.escape(req)}($|\W)")
    return any(pattern.search(h) or re.search(rf"(^|\W){re.escape(h)}($|\W)", req)
               for h in have if len(h) > 2 and len(req) > 2)


def compare(resume: dict, jd: dict, topics_by_slug: dict[str, Topic]) -> dict:
    """Job readiness % = weighted share of JD requirements evidenced on the resume.

    required skills weigh 2, technologies 1 (duplicates counted once, as required).
    """
    have = resume_skill_set(resume)
    reqs: dict[str, int] = {}
    for s in jd.get("technologies", []):
        reqs[norm_skill(s)] = 1
    for s in jd.get("required_skills", []):
        reqs[norm_skill(s)] = 2
    reqs.pop("", None)
    matched = {r: w for r, w in reqs.items() if _matches(r, have)}
    missing = {r: w for r, w in reqs.items() if r not in matched}
    total = sum(reqs.values())
    pct = round(100 * sum(matched.values()) / total, 1) if total else 0.0

    def remediation(skill: str) -> dict:
        slug = SKILL_TOPIC.get(skill)
        t = topics_by_slug.get(slug) if slug else None
        if t:
            return {"skill": skill, "weight": missing[skill], "action": "study",
                    "topic_id": t.id, "topic": t.name,
                    "suggestion": f"Build this up in Study mode: {t.name} ({t.area})."}
        return {"skill": skill, "weight": missing[skill], "action": "project",
                "suggestion": f"Add a small project that uses {skill}, or list it on your "
                              "resume if you already have real experience with it."}

    return {
        "job_readiness": pct,
        "matched": sorted(matched), "missing": [remediation(m) for m in
                                                 sorted(missing, key=lambda m: -missing[m])],
        "resume_skills": sorted(have), "requirements": [{"skill": r, "weight": w}
                                                        for r, w in reqs.items()],
        "method": "deterministic: required skills ×2, technologies ×1; aliases normalised",
    }


async def topics_by_slug(db: AsyncSession) -> dict[str, Topic]:
    from sqlalchemy import select

    return {t.slug: t for t in (await db.scalars(select(Topic))).all()}
