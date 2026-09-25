"""AI Tutor — six bounded modes, each with its own prompt and output contract.

explain · hint · interviewer · evaluate · follow-up · revision
(+ teach_topic, the RAG-grounded explanation/worked example used inside Study Mode)

Every mode goes through the guardrail pipeline and returns the same envelope:
  {mode, data, citations, grounded, checks, model, mock, cached}
"""

import json

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Question, Submission, Topic
from app.routers.common import subtree_topic_ids
from app.services import llm, rag
from app.services.guardrails import (
    SYSTEM_BASE,
    Checks,
    GuardrailError,
    check_citations,
    check_output_safety,
    clean_input,
    forbidden_fragments,
    leaks,
    sources_block,
    wrap_student,
)
from app.services.verdicts import INCORRECT

# ---------------- output contracts ----------------


class ExplainOut(BaseModel):
    explanation: str = Field(min_length=1, max_length=3000)
    key_points: list[str] = Field(min_length=1, max_length=6)
    example: str = Field(max_length=1500)
    citations: list[str] = Field(max_length=8)


class WorkedExampleOut(BaseModel):
    problem: str = Field(min_length=1, max_length=1000)
    steps: list[str] = Field(min_length=2, max_length=8)
    answer: str = Field(min_length=1, max_length=500)
    citations: list[str] = Field(max_length=8)


class HintOut(BaseModel):
    hint: str = Field(min_length=1, max_length=800)
    next_step: str = Field(min_length=1, max_length=400)
    reveals_answer: bool
    citations: list[str] = Field(max_length=8)


class InterviewerOut(BaseModel):
    question: str = Field(min_length=1, max_length=1200)
    expected_concepts: list[str] = Field(min_length=2, max_length=6)
    follow_up_areas: list[str] = Field(min_length=1, max_length=4)
    citations: list[str] = Field(max_length=8)


class EvaluateOut(BaseModel):
    score: int = Field(ge=0, le=10)
    covered_concepts: list[str] = Field(max_length=10)
    missing_concepts: list[str] = Field(max_length=10)
    feedback: str = Field(min_length=1, max_length=1500)
    citations: list[str] = Field(max_length=8)


class FollowupOut(BaseModel):
    question: str = Field(min_length=1, max_length=800)
    why: str = Field(min_length=1, max_length=400)
    citations: list[str] = Field(max_length=8)


class RevisionItem(BaseModel):
    based_on_question_id: int
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=600)
    explanation: str = Field(min_length=1, max_length=800)


class RevisionOut(BaseModel):
    items: list[RevisionItem] = Field(min_length=1, max_length=5)
    citations: list[str] = Field(max_length=10)


# ---------------- pipeline ----------------


def _citation_view(chunks: list[rag.Chunk]) -> list[dict]:
    return [{"id": c.id, "ref": c.ref, "title": c.title, "topic": c.topic,
             "company": c.company, "source_uri": c.source_uri, "score": c.score,
             "snippet": c.content[:220]} for c in chunks]


async def _run(db: AsyncSession, *, user_id: int, mode: str, task: str, instructions: str,
               body: str, output: type[BaseModel], chunks: list[rag.Chunk], checks: Checks,
               cache_key: str | None = None, text_fields: tuple[str, ...] = ()) -> dict:
    prompt = f"{sources_block(chunks)}\n\nTASK ({mode}):\n{instructions}\n\n{body}"
    ck = None
    if cache_key:
        ck = f"{cache_key}|{','.join(str(c.id) for c in chunks)}"
    data, info = await llm.structured(db, user_id=user_id, task=task, system=SYSTEM_BASE,
                                      prompt=prompt, output=output, cache_key=ck,
                                      meta={"mode": mode, "chunks": [c.id for c in chunks]})
    kept = check_citations(getattr(data, "citations", []), chunks, checks)
    check_output_safety([str(getattr(data, f, "")) for f in text_fields], checks)
    return {"mode": mode, "data": data.model_dump(), "citations": _citation_view(kept),
            "grounded": checks.grounded, "checks": checks.as_dict(), **info}


async def _topic_scope(db: AsyncSession, topic_id: int | None) -> tuple[Topic | None, list[int]]:
    if not topic_id:
        return None, []
    t = await db.get(Topic, topic_id)
    if t is None:
        raise GuardrailError("Unknown topic")
    ids = await subtree_topic_ids(db, t.id)
    if t.parent_id:
        ids.append(t.parent_id)
    return t, ids


# ---------------- modes ----------------


async def explain(db: AsyncSession, user_id: int, query: str, topic_id: int | None = None,
                  company_id: int | None = None) -> dict:
    checks = Checks()
    q = clean_input(query, checks, max_chars=800, field_name="question")
    if len(q) < 3:
        raise GuardrailError("Ask a question of at least a few words")
    topic, scope = await _topic_scope(db, topic_id)
    search_q = f"{topic.name}: {q}" if topic else q
    chunks = await rag.search(db, search_q, k=5, topic_ids=scope, company_id=company_id,
                              user_id=user_id)
    if not chunks:
        checks.notes.append("no relevant sources — LLM not called")
        return {"mode": "explain", "data": {
            "explanation": "The course knowledge base doesn't cover this yet, so I won't guess. "
                           "Try rephrasing, or ask about a topic from the syllabus.",
            "key_points": [], "example": "", "citations": []},
            "citations": [], "grounded": False, "checks": checks.as_dict(), "model": None,
            "mock": llm.is_mock(), "cached": False}
    return await _run(
        db, user_id=user_id, mode="explain", task="explain", output=ExplainOut, chunks=chunks,
        checks=checks, cache_key=f"explain|{topic_id}|{q.lower()}",
        text_fields=("explanation", "example"),
        instructions="Give a grounded, beginner-level explanation of the student's question. "
                     "Include 2-5 key points and one short concrete example.",
        body=wrap_student(q))


async def teach_topic(db: AsyncSession, user_id: int, topic: Topic, kind: str) -> dict:
    """Study Mode: RAG-grounded explanation or worked example for a topic."""
    checks = Checks()
    _, scope = await _topic_scope(db, topic.id)
    chunks = await rag.search(db, f"{topic.area} {topic.name} {kind.replace('_', ' ')}", k=4,
                              topic_ids=scope, user_id=user_id)
    if not chunks:
        raise GuardrailError("No knowledge-base sources for this topic")
    if kind == "explanation":
        return await _run(
            db, user_id=user_id, mode="study_explanation", task="explain", output=ExplainOut,
            chunks=chunks, checks=checks, cache_key=f"teach|{topic.id}|explanation",
            text_fields=("explanation", "example"),
            instructions=f"Teach the topic '{topic.name}' ({topic.area}) to a student preparing "
                         "for placement interviews: the core idea, when to use it, and pitfalls. "
                         "2-5 key points, one short example.",
            body="")
    return await _run(
        db, user_id=user_id, mode="study_worked_example", task="explain",
        output=WorkedExampleOut, chunks=chunks, checks=checks,
        cache_key=f"teach|{topic.id}|worked_example", text_fields=("problem", "answer"),
        instructions=f"Create one small worked example for '{topic.name}' ({topic.area}) with "
                     "numbered reasoning steps and the final answer, based on the sources.",
        body="")


async def hint(db: AsyncSession, user_id: int, question_id: int,
               attempt_text: str | None = None) -> dict:
    """A directional hint that must never contain the answer (enforced in code)."""
    checks = Checks()
    q = await db.get(Question, question_id)
    if q is None or q.status != "published":
        raise GuardrailError("Question not found")
    attempt = clean_input(attempt_text, checks, max_chars=2000, field_name="attempt")
    _, scope = await _topic_scope(db, q.topic_id)
    chunks = await rag.search(db, f"{q.title} {q.body}", k=3, topic_ids=scope, user_id=user_id)
    forbidden = forbidden_fragments(q.type, q.options or [], q.answer or {})
    options = "\n".join(f"{o['id']}) {o['text']}" for o in (q.options or []))
    body = (f"QUESTION ({q.type}, {q.difficulty}): {q.title}\n{q.body}\n{options}\n"
            f"{json.dumps({k: v for k, v in (q.meta or {}).items() if k != 'samples'})[:1500]}\n"
            f"CONFIDENTIAL ANSWER KEY (never reveal, quote or paraphrase it): "
            f"{json.dumps(q.answer or {})[:600]}\n"
            + (f"STUDENT'S ATTEMPT SO FAR:\n{wrap_student(attempt)}" if attempt else ""))
    instructions = ("Give ONE directional hint that moves the student one step closer without "
                    "giving the answer: no final value, no correct option, no full code or "
                    "query. Set reveals_answer=true if your hint would give the answer away.")
    out = None
    for attempt_no in range(2):
        out = await _run(db, user_id=user_id, mode="hint", task="hint", output=HintOut,
                         chunks=chunks, checks=checks, text_fields=("hint", "next_step"),
                         instructions=instructions if attempt_no == 0 else instructions +
                         " Your previous hint leaked the answer. Be strictly more general.",
                         body=body)
        text = f"{out['data']['hint']} {out['data']['next_step']}"
        hits = leaks(text, forbidden)
        if not hits and not out["data"]["reveals_answer"]:
            out["checks"]["hint_leak"] = "pass"
            return out
        checks.notes.append(f"hint attempt {attempt_no + 1} withheld: leaked answer")
    # Both attempts leaked: fall back to a safe, generic hint rather than exposing the key.
    out["data"] = {"hint": _generic_hint(q), "next_step": "Re-read the explanation, then try "
                   "eliminating options that contradict it.", "reveals_answer": False,
                   "citations": []}
    out["citations"], out["grounded"] = [], False
    out["checks"] = {**checks.as_dict(), "hint_leak": "blocked_fallback"}
    return out


def _generic_hint(q: Question) -> str:
    topic = q.topic.name if q.topic else "this topic"
    return {
        "mcq": f"Recall the defining property of {topic}; which option is consistent with it?",
        "multi_select": f"Check each statement independently against the definition of {topic}.",
        "numerical": "Write down what quantity is being asked for and the formula that "
                     "connects it to the given values before calculating.",
        "coding": "Start from a brute-force approach, then look for repeated work you can avoid.",
        "sql": "Identify which table(s) hold the data and whether you need grouping or a "
               "subquery.",
    }.get(q.type, f"Revisit the core idea of {topic} and apply it step by step.")


async def interviewer(db: AsyncSession, user_id: int, company_id: int | None,
                      difficulty: str, topic_id: int | None = None) -> dict:
    checks = Checks()
    company = await db.get(Company, company_id) if company_id else None
    topic, scope = await _topic_scope(db, topic_id)
    focus = topic.name if topic else ", ".join(
        (company.oa_pattern or {}).get("frequent_topics", [])[:4]) if company else "core CS"
    chunks = await rag.search(db, f"interview question {focus} {company.name if company else ''}",
                              k=4, topic_ids=scope, company_id=company_id, user_id=user_id)
    pattern = (f"Company: {company.name}. Observed emphasis (not official): "
               f"{json.dumps(company.skill_weights)}; frequently tested: "
               f"{', '.join((company.oa_pattern or {}).get('frequent_topics', []))}."
               if company else "No specific company.")
    return await _run(
        db, user_id=user_id, mode="interviewer", task="interviewer", output=InterviewerOut,
        chunks=chunks, checks=checks, text_fields=("question",),
        instructions=f"Act as a technical interviewer. Ask ONE {difficulty} interview question "
                     f"on {focus}. List the concepts a strong answer covers and 1-3 areas you "
                     "would probe next. Do not answer it.",
        body=pattern)


async def evaluate(db: AsyncSession, user_id: int, question: str, answer: str,
                   expected_concepts: list[str] | None = None,
                   question_id: int | None = None) -> dict:
    checks = Checks()
    qtext = clean_input(question, checks, max_chars=1500, field_name="question")
    ans = clean_input(answer, checks, max_chars=4000, field_name="answer")
    if not ans:
        raise GuardrailError("Write an answer to evaluate")
    concepts = [clean_input(c, checks, max_chars=200) for c in (expected_concepts or [])][:8]
    scope: list[int] = []
    if question_id:
        q = await db.get(Question, question_id)
        if q is not None:
            concepts = concepts or list((q.answer or {}).get("key_points", []))
            _, scope = await _topic_scope(db, q.topic_id)
    chunks = await rag.search(db, qtext, k=4, topic_ids=scope, user_id=user_id)
    return await _run(
        db, user_id=user_id, mode="evaluate", task="evaluate", output=EvaluateOut,
        chunks=chunks, checks=checks, text_fields=("feedback",),
        instructions="Score the student's answer 0-10 for technical accuracy and completeness "
                     "against the expected concepts and sources. List covered and missing "
                     "concepts and give specific, kind feedback. Judge the content, not "
                     "grammar.",
        body=f"QUESTION:\n{wrap_student(qtext)}\nEXPECTED CONCEPTS: "
             f"{json.dumps(concepts) if concepts else '(infer from sources)'}\n"
             f"STUDENT ANSWER:\n{wrap_student(ans)}")


async def followup(db: AsyncSession, user_id: int, previous_question: str,
                   previous_answer: str, topic_id: int | None = None) -> dict:
    checks = Checks()
    pq = clean_input(previous_question, checks, max_chars=1500, field_name="previous question")
    pa = clean_input(previous_answer, checks, max_chars=3000, field_name="previous answer")
    _, scope = await _topic_scope(db, topic_id)
    chunks = await rag.search(db, f"{pq} {pa}", k=4, topic_ids=scope, user_id=user_id)
    return await _run(
        db, user_id=user_id, mode="followup", task="followup", output=FollowupOut,
        chunks=chunks, checks=checks, text_fields=("question",),
        instructions="Ask ONE deeper follow-up question that builds on the previous exchange "
                     "(probe an edge case, a trade-off or the 'why'). Explain briefly why it "
                     "is a good next question. Do not answer it.",
        body=f"PREVIOUS QUESTION:\n{wrap_student(pq)}\nSTUDENT'S ANSWER:\n{wrap_student(pa)}")


async def revision(db: AsyncSession, user_id: int, limit: int = 3) -> dict:
    """Practice questions targeting the student's previously-incorrect items."""
    checks = Checks()
    subs = (await db.scalars(select(Submission).where(
        Submission.user_id == user_id, Submission.mode != "run")
        .order_by(Submission.created_at.desc()).limit(200))).all()
    wrong_ids: list[int] = []
    for s in subs:
        if s.verdict and s.verdict.status in INCORRECT and s.question_id not in wrong_ids:
            wrong_ids.append(s.question_id)
    wrong_ids = wrong_ids[:limit]
    if not wrong_ids:
        raise GuardrailError("No incorrect answers yet — revision mode needs something to revise")
    qs = (await db.scalars(select(Question).where(Question.id.in_(wrong_ids)))).unique().all()
    topic_ids = [q.topic_id for q in qs if q.topic_id]
    chunks = await rag.search(db, " ".join(q.title for q in qs), k=5, topic_ids=topic_ids,
                              user_id=user_id)
    items = "\n\n".join(
        f"[Q{q.id}] ({q.type}, topic: {q.topic.name if q.topic else '-'}) {q.title}: {q.body}\n"
        f"Correct answer: {json.dumps({k: v for k, v in (q.answer or {}).items() if k != 'hidden_tests'})[:400]}\n"  # noqa: E501
        f"Explanation: {q.explanation[:400]}" for q in qs)
    return await _run(
        db, user_id=user_id, mode="revision", task="revision", output=RevisionOut,
        chunks=chunks, checks=checks,
        instructions="For each item the student got wrong, write ONE new short practice "
                     "question on the same concept (not a copy), with its answer and a brief "
                     "explanation. Set based_on_question_id to the [Q#] number.",
        body=f"ITEMS THE STUDENT GOT WRONG:\n{items}")


def block_to_teaching(env: dict, kind: str) -> dict:
    """Convert a teach_topic envelope into Study Mode's TeachingBlock shape."""
    d = env["data"]
    if kind == "explanation":
        body = d["explanation"]
        if d.get("key_points"):
            body += "\n\n" + "\n".join(f"**•** {p}" for p in d["key_points"])
        if d.get("example"):
            body += f"\n\n**Example.** {d['example']}"
        title = "Explanation"
    else:
        body = f"**Problem.** {d['problem']}\n\n" + "\n".join(
            f"{i + 1}. {s}" for i, s in enumerate(d["steps"])) + f"\n\n**Answer.** {d['answer']}"
        title = "Worked example"
    return {"kind": kind, "title": title, "body": body, "grounded": env["grounded"],
            "provider": "rag" + ("-mock" if env.get("mock") else ""),
            "sources": [{"document_id": c["id"], "title": c["title"]} for c in env["citations"]],
            "checks": env["checks"]}
