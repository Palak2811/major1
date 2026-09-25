"""AI question generation → validation → admin review queue.

Generated questions are stored with status="review" and source="ai". They are invisible to
students (only status="published" is ever served) until a content manager approves them —
and approval is refused unless every automated check passed.

Checks recorded in question.meta["review"]["checks"]:
  schema      — the model output matched the JSON contract (Pydantic)
  contract    — the question satisfies the same per-type contract as hand-written questions
  citations   — at least one cited source was actually retrieved
  safety      — no unsafe content
  consistency — (coding) the reference solution is Accepted by Judge0 on every sample AND
                hidden test; (mcq) exactly one correct option, options distinct
"""

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Question, Topic
from app.schemas import QuestionIn
from app.services import jobs, llm, rag
from app.services.guardrails import (
    SYSTEM_BASE,
    Checks,
    GuardrailError,
    check_citations,
    check_output_safety,
    sources_block,
)
from app.services.judge import ACCEPTED, Case, aggregate, get_judge


class GenMCQ(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    body: str = Field(min_length=10, max_length=2000)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=10, max_length=1500)
    citations: list[str] = Field(max_length=6)


class IOCase(BaseModel):
    input: str = Field(max_length=2000)
    output: str = Field(min_length=1, max_length=2000)


class GenCoding(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    statement: str = Field(min_length=20, max_length=4000)
    constraints: str = Field(min_length=3, max_length=1000)
    input_format: str = Field(min_length=3, max_length=1000)
    output_format: str = Field(min_length=3, max_length=1000)
    samples: list[IOCase] = Field(min_length=1, max_length=3)
    hidden_tests: list[IOCase] = Field(min_length=3, max_length=8)
    reference_solution_python: str = Field(min_length=10, max_length=6000)
    explanation: str = Field(min_length=10, max_length=1500)
    citations: list[str] = Field(max_length=6)


async def generate(db: AsyncSession, *, user_id: int, topic_id: int, qtype: str,
                   difficulty: str) -> Question:
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise GuardrailError("Unknown topic")
    checks = Checks()
    chunks = await rag.search(db, f"{topic.area} {topic.name}", k=5, topic_ids=[topic.id],
                              user_id=user_id)
    if not chunks:
        raise GuardrailError("No knowledge-base sources for this topic — add material first")
    if qtype == "mcq":
        output, task_text = GenMCQ, (
            f"Write ONE {difficulty} multiple-choice question on '{topic.name}' ({topic.area}) "
            "for placement preparation, strictly based on the sources. Exactly 4 distinct "
            "options, exactly one correct (give its 0-based index), and an explanation.")
    else:
        output, task_text = GenCoding, (
            f"Write ONE {difficulty} stdin/stdout coding problem on '{topic.name}' "
            f"({topic.area}). Provide statement, constraints, input/output formats, 1-3 samples, "
            "3-8 hidden tests (edge cases included) and a correct Python 3 reference solution "
            "that reads stdin and prints exactly the expected output.")
    data, info = await llm.structured(
        db, user_id=user_id, task="generate_question", system=SYSTEM_BASE,
        prompt=f"{sources_block(chunks)}\n\nTASK:\n{task_text}", output=output,
        temperature=0.7, meta={"topic_id": topic.id, "type": qtype})
    kept = check_citations(data.citations, chunks, checks)
    review = {"generated_by": info["model"], "mock": info["mock"], "requested_by": user_id,
              "citations": [{"id": c.id, "title": c.title} for c in kept],
              "checks": {"schema": "pass"}, "status": "pending_checks"}
    try:
        check_output_safety([data.title, getattr(data, "body", getattr(data, "statement", ""))],
                            checks)
        review["checks"]["safety"] = "pass"
    except GuardrailError:
        review["checks"]["safety"] = "fail"
    review["checks"]["citations"] = "pass" if checks.grounded else "fail"

    if isinstance(data, GenMCQ):
        distinct = len({o.strip().lower() for o in data.options}) == 4
        review["checks"]["consistency"] = "pass" if distinct else "fail: duplicate options"
        fields = dict(type="mcq", title=data.title, body=data.body, difficulty=difficulty,
                      topic_id=topic.id,
                      options=[{"id": "abcd"[i], "text": t} for i, t in enumerate(data.options)],
                      answer={"correct": ["abcd"[data.correct_index]]},
                      explanation=data.explanation, meta={})
    else:
        fields = dict(type="coding", title=data.title, body=data.statement, difficulty=difficulty,
                      topic_id=topic.id, explanation=data.explanation,
                      meta={"constraints": data.constraints, "input_format": data.input_format,
                            "output_format": data.output_format,
                            "samples": [c.model_dump() for c in data.samples],
                            "time_limit_ms": 2000, "memory_limit_mb": 256},
                      answer={"hidden_tests": [c.model_dump() for c in data.hidden_tests],
                              "reference_solution": {"language": "python",
                                                     "code": data.reference_solution_python}})
        review["checks"]["consistency"] = "pending: reference solution queued for Judge0"
    try:
        QuestionIn.model_validate({**fields, "status": "draft"})
        review["checks"]["contract"] = "pass"
    except ValidationError as e:
        review["checks"]["contract"] = f"fail: {e.errors()[0]['msg']}"

    q = Question(**fields, status="review", source="ai", created_by=user_id)
    q.meta = {**q.meta, "review": review}
    _settle(q)
    db.add(q)
    await db.flush()
    if fields["type"] == "coding" and review["checks"]["contract"] == "pass":
        jobs.enqueue("validate_generated_coding", question_id=q.id)
    return q


def _settle(q: Question) -> None:
    """Auto-reject on any failed check; mark ready when every check passed."""
    review = q.meta["review"]
    results = review["checks"].values()
    if any(str(v).startswith("fail") for v in results):
        review["status"] = "auto_rejected"
        q.status = "rejected"
    elif all(v == "pass" for v in results):
        review["status"] = "ready_for_review"
    q.meta = {**q.meta, "review": review}


@jobs.job("validate_generated_coding")
async def validate_generated_coding(question_id: int) -> None:
    """Run the AI's reference solution on Judge0 against its own samples + hidden tests."""
    async with jobs.session_factory() as db:
        q = await db.get(Question, question_id)
        if q is None or q.source != "ai":
            return
        ref = (q.answer or {}).get("reference_solution", {})
        cases = [Case(c["input"], c["output"], True) for c in q.meta.get("samples", [])] + \
                [Case(c["input"], c["output"], False) for c in q.answer.get("hidden_tests", [])]
        review = dict(q.meta["review"])
        try:
            res = await get_judge().execute(ref.get("language", "python"), ref.get("code", ""),
                                            cases, 2.0, 262144)
            o = aggregate(res, cases)
            review["checks"] = {**review["checks"], "consistency": "pass" if o.verdict == ACCEPTED
                                else f"fail: reference solution got {o.verdict} "
                                     f"({o.passed}/{o.total} tests)"}
        except Exception as e:  # sandbox unreachable: leave pending, admin can re-run
            review["checks"] = {**review["checks"],
                                "consistency": f"pending: judge unavailable ({type(e).__name__})"}
        q.meta = {**q.meta, "review": review}
        _settle(q)
        await db.commit()


def can_publish(q: Question) -> tuple[bool, str]:
    review = (q.meta or {}).get("review", {})
    bad = {k: v for k, v in review.get("checks", {}).items() if v != "pass"}
    if bad:
        return False, "Checks not passed: " + "; ".join(f"{k}={v}" for k, v in bad.items())
    return True, ""

