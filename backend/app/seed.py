"""Idempotent seed: roles, staff accounts, topic taxonomy, skill graph roots,
sample companies and questions. Run: `python -m app.seed`."""

import asyncio
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import ROLE_SCOPES, hash_password
from app.models import (
    Company,
    Document,
    Profile,
    Question,
    Role,
    Skill,
    Test,
    TestQuestion,
    Topic,
    User,
)
from app.routers.util import slugify
from app.seed_content import (
    CODING_PROBLEMS,
    DOCS,
    KB_DOCS,
    QUESTIONS,
    SAMPLE_TEST,
    SECOND_HIGHEST_SEED,
    SQL_PROBLEMS,
)
from app.services import llm, rag
from app.services.composition import Candidate, balance

ROLE_DESCRIPTIONS = {
    "student": "Learner preparing for placements",
    "content_manager": "Curates questions, topics and company patterns",
    "admin": "Full platform administration",
}

TOPICS: dict[str, list[tuple[str, list[str]]]] = {
    "DSA": [
        ("Arrays", ["Two Pointer", "Sliding Window", "Prefix Sum"]),
        ("Trees", ["Tree Traversal", "Binary Search Tree", "Lowest Common Ancestor"]),
        ("Graphs", ["BFS", "DFS", "Dijkstra", "Disjoint Set Union"]),
        ("Dynamic Programming", ["1D DP", "2D DP", "Knapsack"]),
    ],
    "DBMS": [("SQL", ["Joins", "Aggregation"]), ("Normalization", []), ("Transactions", [])],
    "OS": [("Processes & Threads", []), ("CPU Scheduling", []), ("Memory Management", []),
           ("Deadlocks", [])],
    "CN": [("OSI & TCP/IP", []), ("Transport Layer", []), ("Application Layer", [])],
    "OOP": [("Principles", ["Inheritance", "Polymorphism", "Encapsulation"]),
            ("Design Patterns", [])],
    "Aptitude": [("Quantitative", ["Percentages", "Time & Work", "Probability"]),
                 ("Logical Reasoning", [])],
}

COMPANIES = [
    {
        "name": "Amazon",
        "description": "Product company; SDE-1 campus hiring emphasises DSA and "
                       "leadership principles.",
        "skill_weights": {"dsa": 50, "oop": 10, "dbms": 10, "os": 10, "aptitude": 5, "hr": 15},
        "oa_pattern": {"coding_questions": 2, "mcqs": 0, "duration_minutes": 90,
                       "difficulty": "medium",
                       "frequent_topics": ["Arrays", "Graphs", "Dynamic Programming", "Trees"]},
    },
    {
        "name": "TCS",
        "description": "Services company; NQT-style assessment with a strong aptitude section.",
        "skill_weights": {"dsa": 20, "oop": 10, "dbms": 10, "os": 5, "aptitude": 40, "hr": 15},
        "oa_pattern": {"coding_questions": 2, "mcqs": 65, "duration_minutes": 180,
                       "difficulty": "easy",
                       "frequent_topics": ["Quantitative", "Logical Reasoning", "Arrays"]},
        "readiness_weights": {"dsa": 0.15, "csf": 0.15, "coding": 0.15, "aptitude": 0.30,
                              "interview": 0.15, "consistency": 0.10},
    },
    {
        "name": "Microsoft",
        "description": "Product company; OA followed by multiple technical interview rounds.",
        "skill_weights": {"dsa": 45, "oop": 15, "dbms": 10, "os": 15, "aptitude": 0, "hr": 15},
        "oa_pattern": {"coding_questions": 3, "mcqs": 0, "duration_minutes": 90,
                       "difficulty": "hard",
                       "frequent_topics": ["Trees", "Dynamic Programming", "Graphs"]},
    },
]


def _questions(t: dict[str, Topic], c: dict[str, Company]) -> list[dict]:
    return [
        dict(type="mcq", title="Time complexity of BFS", difficulty="easy",
             topic=t["bfs"], companies=[c["amazon"], c["microsoft"]],
             body="What is the time complexity of BFS on a graph with V vertices and E edges "
                  "stored as an adjacency list?",
             options=[{"id": "a", "text": "O(V)"}, {"id": "b", "text": "O(V + E)"},
                      {"id": "c", "text": "O(V·E)"}, {"id": "d", "text": "O(E log V)"}],
             answer={"correct": ["b"]},
             explanation="Each vertex is enqueued once and each edge is examined once "
                         "(twice for undirected graphs), giving O(V + E)."),
        dict(type="multi_select", title="Properties of a B+ tree", difficulty="medium",
             topic=t["normalization"], companies=[c["microsoft"]],
             body="Which statements about B+ trees used for database indexes are true?",
             options=[{"id": "a", "text": "All records live in leaf nodes"},
                      {"id": "b", "text": "Leaves are linked for range scans"},
                      {"id": "c", "text": "Internal nodes store full records"},
                      {"id": "d", "text": "The tree stays height-balanced"}],
             answer={"correct": ["a", "b", "d"]},
             explanation="Internal nodes hold only keys for routing; data is in linked leaves."),
        dict(type="numerical", title="Work together", difficulty="easy",
             topic=t["time-work"], companies=[c["tcs"]],
             body="A finishes a job in 10 days and B in 15 days. Working together, in how many "
                  "days do they finish?",
             answer={"value": 6, "tolerance": 0},
             explanation="Combined rate = 1/10 + 1/15 = 1/6 per day, so 6 days."),
        dict(type="output_prediction", title="Mutable default argument", difficulty="medium",
             topic=t["polymorphism"], companies=[],
             body="What does this Python snippet print?",
             meta={"code": "def f(x, acc=[]):\n    acc.append(x)\n    return acc\n\n"
                           "f(1)\nprint(f(2))", "language": "python"},
             answer={"expected_output": "[1, 2]"},
             explanation="Default arguments are evaluated once, so `acc` is shared across calls."),
        dict(type="coding", title="Two Sum (sorted input)", difficulty="easy",
             topic=t["two-pointer"], companies=[c["amazon"], c["tcs"]],
             body="Given a sorted array `nums` and an integer `target`, return the 1-based "
                  "indices of the two numbers that add up to `target`.",
             meta={"constraints": "2 ≤ n ≤ 10^5; -10^9 ≤ nums[i], target ≤ 10^9; exactly one "
                                  "solution exists.",
                   "input_format": "Line 1: n and target. Line 2: n space-separated integers.",
                   "output_format": "Two space-separated indices i < j.",
                   "samples": [{"input": "4 9\n2 7 11 15", "output": "1 2"}],
                   "time_limit_ms": 2000, "memory_limit_mb": 256},
             answer={"hidden_tests": [{"input": "3 6\n1 2 4", "output": "2 3"},
                                      {"input": "2 -1\n-3 2", "output": "1 2"}]},
             explanation="Move two pointers inward from both ends: O(n) time, O(1) space."),
        dict(type="sql", title="Second highest salary", difficulty="medium",
             topic=t["aggregation"], companies=[c["amazon"]],
             body="Write a query returning the second highest distinct salary from `employees` "
                  "as `second_highest` (NULL if none).",
             meta={"schema_sql": "CREATE TABLE employees (id INT PRIMARY KEY, salary INT);"},
             answer={"reference_query": "SELECT MAX(salary) AS second_highest FROM employees "
                                        "WHERE salary < (SELECT MAX(salary) FROM employees);"}),
        dict(type="debugging", title="Off-by-one in binary search", difficulty="easy",
             topic=t["arrays"], companies=[],
             body="This binary search loops forever for some inputs. Identify and fix the bug.",
             meta={"code": "def search(a, x):\n    lo, hi = 0, len(a) - 1\n    while lo < hi:\n"
                           "        mid = (lo + hi) // 2\n        if a[mid] < x:\n"
                           "            lo = mid\n        else:\n            hi = mid\n"
                           "    return lo", "language": "python"},
             answer={"fix": "lo = mid + 1"},
             explanation="When a[mid] < x, `lo = mid` can stall; it must advance to mid + 1."),
        dict(type="theory", title="Process vs thread", difficulty="easy",
             topic=t["processes-threads"], companies=[c["microsoft"], c["tcs"]],
             body="Explain the difference between a process and a thread.",
             answer={"key_points": ["separate address space vs shared", "context switch cost",
                                    "threads share heap/code, have own stack", "isolation"]}),
    ]


async def _role(db: AsyncSession, name: str) -> Role:
    role = await db.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name)
        db.add(role)
    role.description = ROLE_DESCRIPTIONS[name]
    role.scopes = ROLE_SCOPES[name]
    return role


async def _user(db: AsyncSession, email: str, name: str, password: str, role: Role):
    if not await db.scalar(select(User.id).where(User.email == email)):
        u = User(email=email, full_name=name, password_hash=hash_password(password), role=role)
        u.profile = Profile()
        db.add(u)


async def seed() -> None:
    s = get_settings()
    async with SessionLocal() as db:
        roles = {n: await _role(db, n) for n in ROLE_SCOPES}
        await db.flush()
        await _user(db, s.seed_admin_email, "Platform Admin", s.seed_admin_password,
                    roles["admin"])
        await _user(db, "content@preppath.dev", "Content Manager", "ChangeMe-Content1",
                    roles["content_manager"])
        await _user(db, "student@preppath.dev", "Demo Student", "ChangeMe-Student1",
                    roles["student"])

        topics: dict[str, Topic] = {}
        skills: dict[str, Skill] = {}

        async def topic(name: str, area: str, parent: Topic | None) -> Topic:
            slug = slugify(name)
            t = await db.scalar(select(Topic).where(Topic.slug == slug))
            if t is None:
                t = Topic(name=name, slug=slug, area=area,
                          parent_id=parent.id if parent else None)
                db.add(t)
                await db.flush()
            sk = await db.scalar(select(Skill).where(Skill.slug == slug))
            if sk is None:
                parent_skill = skills.get(slugify(parent.name)) if parent else skills[area.lower()]
                sk = Skill(name=name, slug=slug, area=area, topic_id=t.id,
                           parent_id=parent_skill.id if parent_skill else None)
                db.add(sk)
                await db.flush()
            skills[slug] = sk
            topics[slug] = t
            return t

        for area, groups in TOPICS.items():
            root = await db.scalar(select(Skill).where(Skill.slug == area.lower()))
            if root is None:
                root = Skill(name=area, slug=area.lower(), area=area)
                db.add(root)
                await db.flush()
            skills[area.lower()] = root
            for name, children in groups:
                parent = await topic(name, area, None)
                for child in children:
                    await topic(child, area, parent)
        companies: dict[str, Company] = {}
        for data in COMPANIES:
            slug = slugify(data["name"])
            c = await db.scalar(select(Company).where(Company.slug == slug))
            if c is None:
                c = Company(slug=slug, **data)
                db.add(c)
                await db.flush()
            companies[slug] = c

        for q in _questions(topics, companies):
            if await db.scalar(select(Question.id).where(Question.title == q["title"])):
                continue
            topic_obj = q.pop("topic")
            db.add(Question(**q, topic_id=topic_obj.id, status="published", source="manual"))
        await db.flush()

        await _seed_study_content(db, topics)
        await _seed_sample_test(db, topics)
        await db.commit()
        # Index the knowledge base for RAG (Gemini embeddings, or offline hashing in mock mode).
        try:
            n = await rag.embed_pending(db)
            await db.commit()
            print(f"Embedded {n} knowledge-base chunks ({'mock' if llm.is_mock() else 'gemini'}).")
        except llm.AIError as e:
            await db.rollback()
            print(f"Embedding skipped ({e}); run POST /api/v1/kb/reembed later.")
    print("Seed complete.")


async def _seed_study_content(db: AsyncSession, topics: dict[str, Topic]) -> None:
    for q in QUESTIONS + CODING_PROBLEMS + SQL_PROBLEMS:
        if await db.scalar(select(Question.id).where(Question.title == q["title"])):
            continue
        data = dict(q)
        topic = topics[data.pop("topic")]
        db.add(Question(**data, topic_id=topic.id, status="published", source="manual"))
    # Phase 3: the SQL question needs rows so Judge0 can compare outputs.
    sh = await db.scalar(select(Question).where(Question.title == "Second highest salary"))
    if sh is not None and not (sh.meta or {}).get("seed_sql"):
        sh.meta = {**sh.meta, "seed_sql": SECOND_HIGHEST_SEED}
    for slug, blocks in DOCS.items():
        for kind, title, content in blocks:
            exists = await db.scalar(select(Document.id).where(
                Document.topic_id == topics[slug].id, Document.kind == kind))
            if not exists:
                db.add(Document(title=title, kind=kind, content=content,
                                topic_id=topics[slug].id, source_uri="curated://seed",
                                meta={"source": f"curated:{slug}:{kind}"}))
    for kind, title, slug, text in KB_DOCS:
        if not await db.scalar(select(Document.id).where(Document.title == title)):
            await rag.ingest(db, title=title, text=text, kind=kind,
                             topic_id=topics[slug].id if slug else None,
                             source_uri="curated://seed")
    await db.flush()


def _subtree(all_topics: list[Topic], root_id: int) -> set[int]:
    out, stack = set(), [root_id]
    while stack:
        t = stack.pop()
        out.add(t)
        stack += [x.id for x in all_topics if x.parent_id == t]
    return out


async def _seed_sample_test(db: AsyncSession, topics: dict[str, Topic]) -> None:
    spec = SAMPLE_TEST
    if await db.scalar(select(Test.id).where(Test.title == spec["title"])):
        return
    all_topics = list((await db.scalars(select(Topic))).all())
    rng = random.Random(42)  # deterministic sample test
    t = Test(title=spec["title"], description=spec["description"],
             negative_marking=spec["negative_marking"], randomize=True, is_published=True,
             sections=[{"name": s["name"], "time_limit_seconds": s["time_limit_seconds"]}
                       for s in spec["sections"]],
             duration_seconds=sum(s["time_limit_seconds"] for s in spec["sections"]))
    db.add(t)
    await db.flush()
    pos, used = 0, set()
    for sec in spec["sections"]:
        ids: set[int] = set()
        for slug in sec["topics"]:
            ids |= _subtree(all_topics, topics[slug].id)
        pool = (await db.scalars(select(Question).where(
            Question.status == "published", Question.topic_id.in_(ids),
            Question.type.in_(sec["types"])))).unique().all()
        picked = [c.id for c in balance([Candidate(q.id, q.difficulty, q.topic_id)
                                         for q in pool if q.id not in used],
                                        sec["count"], None, rng)]
        for title in sec.get("extra", []):
            qid = await db.scalar(select(Question.id).where(Question.title == title))
            if qid:
                picked.append(qid)
        for qid in picked:
            used.add(qid)
            db.add(TestQuestion(test_id=t.id, question_id=qid, section=sec["name"],
                                position=pos, marks=1.0,
                                negative_marks=spec["negative_ratio"]))
            pos += 1


if __name__ == "__main__":
    asyncio.run(seed())
