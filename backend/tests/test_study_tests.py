"""Integration tests: full Study Mode cycle and timed Test Mode attempts."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import Attempt
from tests.conftest import login, register


def mcq(title, correct="a", difficulty="easy", topic_id=None):
    return {"type": "mcq", "title": title, "body": f"{title}?", "difficulty": difficulty,
            "topic_id": topic_id, "status": "published", "explanation": f"Because {correct}.",
            "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "answer": {"correct": [correct]}}


async def setup_topic(client, n=6):
    cm = await login(client, "content_manager@t.dev")
    root = (await client.post("/api/v1/topics", json={"name": "Graphs", "area": "DSA"},
                              headers=cm)).json()
    t = (await client.post("/api/v1/topics", json={"name": "BFS", "area": "DSA",
                                                   "parent_id": root["id"]}, headers=cm)).json()
    ids = []
    for i, d in enumerate(["easy", "easy", "medium", "medium", "hard", "hard"][:n]):
        r = await client.post("/api/v1/questions", json=mcq(f"Question {i}", difficulty=d,
                                                            topic_id=t["id"]), headers=cm)
        ids.append(r.json()["id"])
    return cm, t, ids


def answer_for(session, qid, right=True):
    return {"question_id": qid, "time_taken_ms": 30_000,
            "answer": {"selected": ["a" if right else "b"]}}


async def run_cycle(client, h, topic_id, right=True, confidence=4):
    s = (await client.post("/api/v1/study/sessions", json={"topic_id": topic_id},
                           headers=h)).json()
    sid = s["id"]
    s = (await client.post(f"/api/v1/study/sessions/{sid}/answer",
                           json=answer_for(s, s["question"]["id"], right), headers=h)).json()
    if s["followup"]:
        s = (await client.post(f"/api/v1/study/sessions/{sid}/answer",
                               json=answer_for(s, s["followup"]["id"], right), headers=h)).json()
    for q in s["quiz"]:
        s = (await client.post(f"/api/v1/study/sessions/{sid}/answer",
                               json=answer_for(s, q["id"], right), headers=h)).json()
    assert s["stage"] == "confidence"
    r = await client.post(f"/api/v1/study/sessions/{sid}/complete",
                          json={"confidence": confidence}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def test_study_cycle_updates_skill_graph(client):
    _, topic, _ = await setup_topic(client)
    h = await register(client)

    s = (await client.post("/api/v1/study/sessions", json={"topic_id": topic["id"]},
                           headers=h)).json()
    assert s["stage"] == "question" and s["target_difficulty"] == "easy"
    assert s["question"]["difficulty"] == "easy"  # no mastery yet -> start easy
    assert "answer" not in s["question"] or s["question"]["answer"] is None

    # can't skip ahead to the confidence check
    r = await client.post(f"/api/v1/study/sessions/{s['id']}/complete", json={"confidence": 3},
                          headers=h)
    assert r.status_code == 409

    s = (await client.post(f"/api/v1/study/sessions/{s['id']}/answer",
                           json=answer_for(s, s["question"]["id"]), headers=h)).json()
    ans = s["answers"][str(s["question"]["id"])]
    assert ans["correct"] and ans["answer"] == {"correct": ["a"]}  # revealed after answering
    assert s["followup"]["difficulty"] == "medium"  # stepped up after a correct answer
    assert len(s["quiz"]) == 3

    for q in [s["followup"], *s["quiz"]]:
        s = (await client.post(f"/api/v1/study/sessions/{s['id']}/answer",
                               json=answer_for(s, q["id"]), headers=h)).json()
    done = (await client.post(f"/api/v1/study/sessions/{s['id']}/complete",
                              json={"confidence": 4}, headers=h)).json()
    assert done["status"] == "completed"
    change = done["result"]["changes"][0]
    assert change["skill"] == "BFS" and change["after"] > change["before"] == 0

    skills = (await client.get("/api/v1/me/skills", headers=h)).json()
    bfs = next(n for n in skills if n["name"] == "BFS")
    assert bfs["attempt_count"] == 5 and bfs["accuracy"] == 1.0
    assert bfs["confidence"] == 0.75  # self-report stored next to measured accuracy
    graphs = next(n for n in skills if n["name"] == "Graphs")
    assert graphs["rollup"] == pytest.approx(bfs["mastery_score"], abs=0.05)  # rolls up

    dash = (await client.get("/api/v1/me/dashboard", headers=h)).json()
    dsa = next(a for a in dash["areas"] if a["area"] == "DSA")
    assert dsa["mastery"] == pytest.approx(bfs["mastery_score"], abs=0.05)
    assert dash["study_streak"] == 1
    prof = (await client.get("/api/v1/users/me/profile", headers=h)).json()
    assert prof["dsa_score"] == pytest.approx(bfs["mastery_score"], abs=0.05)


async def test_wrong_cycle_lowers_mastery_and_marks_weak(client):
    _, topic, _ = await setup_topic(client)
    h = await register(client)
    first = await run_cycle(client, h, topic["id"], right=True)
    up = first["result"]["changes"][0]["after"]
    second = await run_cycle(client, h, topic["id"], right=False, confidence=5)
    after = second["result"]["changes"][0]["after"]
    assert after < up
    prof = (await client.get("/api/v1/users/me/profile", headers=h)).json()
    assert "BFS" in prof["weak_topics"]


async def test_study_needs_questions(client):
    cm = await login(client, "content_manager@t.dev")
    t = (await client.post("/api/v1/topics", json={"name": "Empty", "area": "OS"},
                           headers=cm)).json()
    h = await register(client)
    r = await client.post("/api/v1/study/sessions", json={"topic_id": t["id"]}, headers=h)
    assert r.status_code == 422


async def make_test(client, cm, ids, **kw):
    body = {"title": "Mock OA", "negative_marking": True, "negative_ratio": 0.25,
            "is_published": True, "randomize": True,
            "sections": [{"name": "Quant", "time_limit_seconds": 600},
                         {"name": "Tech", "time_limit_seconds": 600}],
            "questions": [{"question_id": ids[0], "section": "Quant", "marks": 4},
                          {"question_id": ids[1], "section": "Quant", "marks": 4},
                          {"question_id": ids[2], "section": "Tech", "marks": 4},
                          {"question_id": ids[3], "section": "Tech", "marks": 4}], **kw}
    r = await client.post("/api/v1/tests", json=body, headers=cm)
    assert r.status_code == 201, r.text
    return r.json()


async def test_timed_test_with_negative_marking_and_analysis(client):
    cm, _, ids = await setup_topic(client)
    test = await make_test(client, cm, ids)
    h = await register(client)

    listed = (await client.get("/api/v1/tests", headers=h)).json()
    assert [t["id"] for t in listed] == [test["id"]] and listed[0]["duration_seconds"] == 1200

    a = (await client.post(f"/api/v1/tests/{test['id']}/attempts", headers=h)).json()
    assert len(a["items"]) == 4 and a["sections"][0]["deadline"] < a["sections"][1]["deadline"]
    assert all(it["question"]["answer"] is None for it in a["items"])
    # resume returns the same attempt
    again = (await client.post(f"/api/v1/tests/{test['id']}/attempts", headers=h)).json()
    assert again["id"] == a["id"]

    by_q = {it["question"]["id"]: it["tq_id"] for it in a["items"]}
    url = f"/api/v1/attempts/{a['id']}/answers"
    await client.put(f"{url}/{by_q[ids[0]]}", json={"answer": {"selected": ["a"]},
                                                     "time_spent_ms": 20_000}, headers=h)
    await client.put(f"{url}/{by_q[ids[1]]}", json={"answer": {"selected": ["b"]},
                                                     "time_spent_ms": 15_000}, headers=h)
    r = await client.put(f"{url}/{by_q[ids[2]]}", json={"flagged": True, "time_spent_ms": 5_000},
                         headers=h)
    assert r.json()["flagged"] is True
    # ids[3] left unanswered

    res = (await client.post(f"/api/v1/attempts/{a['id']}/submit", headers=h)).json()
    assert res["score"] == 4 - 1  # +4 correct, -1 (25% of 4) wrong, 0 unanswered
    assert res["max_score"] == 16
    assert res["counts"] == {"correct": 1, "incorrect": 1, "unanswered": 2, "pending": 0}
    quant = next(s for s in res["sections"] if s["name"] == "Quant")
    assert quant["awarded"] == 3 and quant["time_ms"] == 35_000
    wrong = next(i for i in res["items"] if i["question_id"] == ids[1])
    assert wrong["status"] == "incorrect" and wrong["answer"] == {"correct": ["a"]}
    assert next(i for i in res["items"] if i["question_id"] == ids[2])["flagged"] is True

    # submitted attempts are read-only
    r = await client.put(f"{url}/{by_q[ids[3]]}", json={"answer": {"selected": ["a"]}},
                         headers=h)
    assert r.status_code == 409


async def test_coding_question_is_pending_not_scored(client):
    cm, _, ids = await setup_topic(client, n=1)
    q = (await client.post("/api/v1/questions", headers=cm, json={
        "type": "coding", "title": "Echo", "body": "Echo input", "difficulty": "easy",
        "status": "published", "meta": {"constraints": "n<10", "input_format": "n",
                                        "output_format": "n",
                                        "samples": [{"input": "1", "output": "1"}]},
        "answer": {"hidden_tests": [{"input": "2", "output": "2"}]}})).json()
    test = (await client.post("/api/v1/tests", headers=cm, json={
        "title": "Mixed", "is_published": True,
        "questions": [{"question_id": ids[0]}, {"question_id": q["id"], "marks": 10}]})).json()
    h = await register(client)
    a = (await client.post(f"/api/v1/tests/{test['id']}/attempts", headers=h)).json()
    tq = next(i["tq_id"] for i in a["items"] if i["question"]["type"] == "coding")
    await client.put(f"/api/v1/attempts/{a['id']}/answers/{tq}",
                     json={"answer": {"code": "print(input())", "language": "python"}}, headers=h)
    res = (await client.post(f"/api/v1/attempts/{a['id']}/submit", headers=h)).json()
    item = next(i for i in res["items"] if i["type"] == "coding")
    assert item["status"] == "pending" and item["awarded"] == 0
    assert "hidden_tests" not in item["answer"]  # never leaked, even after submission
    assert res["max_score"] == 1  # pending coding marks excluded until Judge0 (Phase 3)


async def test_expired_attempt_auto_submits_with_partial_answers(client, sessionmaker):
    cm, _, ids = await setup_topic(client)
    test = await make_test(client, cm, ids)
    h = await register(client)
    a = (await client.post(f"/api/v1/tests/{test['id']}/attempts", headers=h)).json()
    tq = next(i["tq_id"] for i in a["items"] if i["question"]["id"] == ids[0])
    await client.put(f"/api/v1/attempts/{a['id']}/answers/{tq}",
                     json={"answer": {"selected": ["a"]}}, headers=h)

    # Move the clock: pretend the attempt started 30 minutes ago
    async with sessionmaker() as db:
        att = await db.scalar(select(Attempt).where(Attempt.id == a["id"]))
        st = dict(att.state)
        from datetime import datetime
        shift = timedelta(minutes=30)
        st["deadline"] = (datetime.fromisoformat(st["deadline"]) - shift).isoformat()
        st["sections"] = [{**s, "deadline": (datetime.fromisoformat(s["deadline"]) - shift)
                           .isoformat()} for s in st["sections"]]
        att.state = st
        await db.commit()

    r = await client.put(f"/api/v1/attempts/{a['id']}/answers/{tq}",
                         json={"answer": {"selected": ["b"]}}, headers=h)
    assert r.status_code == 409
    res = (await client.get(f"/api/v1/attempts/{a['id']}/analysis", headers=h)).json()
    assert res["auto_submitted"] is True and res["counts"]["correct"] == 1  # partial answer kept


async def test_compose_balances_difficulty(client):
    cm, topic, _ = await setup_topic(client)
    r = await client.post("/api/v1/tests/compose", headers=cm, json={
        "title": "Auto", "seed": 7,
        "sections": [{"name": "DSA", "topic_ids": [topic["id"]], "count": 4}],
        "mix": {"easy": 0.5, "medium": 0.25, "hard": 0.25}})
    assert r.status_code == 201, r.text
    diffs = sorted(i["question"]["difficulty"] for i in r.json()["items"])
    assert diffs == ["easy", "easy", "hard", "medium"]
    r = await client.post("/api/v1/tests/compose", headers=cm, json={
        "title": "Too big", "sections": [{"name": "X", "topic_ids": [topic["id"]], "count": 50}]})
    assert r.status_code == 422


async def test_students_cannot_author_or_see_unpublished(client):
    cm, _, ids = await setup_topic(client)
    t = await make_test(client, cm, ids, is_published=False)
    h = await register(client)
    assert (await client.get(f"/api/v1/tests/{t['id']}", headers=h)).status_code == 404
    assert (await client.post(f"/api/v1/tests/{t['id']}/attempts", headers=h)).status_code == 404
    assert (await client.post("/api/v1/tests", headers=h, json={
        "title": "x" * 5, "questions": [{"question_id": ids[0]}]})).status_code == 403


async def test_attempts_are_private(client):
    cm, _, ids = await setup_topic(client)
    t = await make_test(client, cm, ids)
    a = await register(client, "a@t.dev")
    b = await register(client, "b@t.dev")
    att = (await client.post(f"/api/v1/tests/{t['id']}/attempts", headers=a)).json()
    assert (await client.get(f"/api/v1/attempts/{att['id']}", headers=b)).status_code == 404


async def test_dashboard_ignores_skipped_questions(client):
    cm, _, ids = await setup_topic(client)
    t = await make_test(client, cm, ids)
    h = await register(client)
    a = (await client.post(f"/api/v1/tests/{t['id']}/attempts", headers=h)).json()
    tq = next(i["tq_id"] for i in a["items"] if i["question"]["id"] == ids[0])
    await client.put(f"/api/v1/attempts/{a['id']}/answers/{tq}",
                     json={"answer": {"selected": ["a"]}}, headers=h)
    await client.post(f"/api/v1/attempts/{a['id']}/submit", headers=h)
    dash = (await client.get("/api/v1/me/dashboard", headers=h)).json()
    assert dash["questions_answered"] == 1 and dash["overall_accuracy"] == 1.0
