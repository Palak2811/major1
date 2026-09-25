"""Phase 3 integration tests: submission pipeline, test-mode judging, readiness, analytics."""

import pytest

from app.services import jobs
from app.services.judge import Case as JCase
from app.services.judge import CaseResult, aggregate, map_status
from app.services.readiness import readiness
from tests.conftest import login, register

CODING = {
    "type": "coding", "title": "Double it", "body": "Print 2n.", "difficulty": "medium",
    "status": "published",
    "meta": {"constraints": "n ≤ 1e9", "input_format": "n", "output_format": "2n",
             "samples": [{"input": "2", "output": "4"}]},
    "answer": {"hidden_tests": [{"input": "SECRET-7", "output": "14"},
                                {"input": "SECRET-0", "output": "0"}]},
}


async def setup(client, area="DSA"):
    cm = await login(client, "content_manager@t.dev")
    topic = (await client.post("/api/v1/topics", json={"name": "Math", "area": area},
                               headers=cm)).json()
    q = (await client.post("/api/v1/questions", json={**CODING, "topic_id": topic["id"]},
                           headers=cm)).json()
    return cm, topic, q


async def submit(client, h, qid, code="#AC", mode="submit", lang="python", **kw):
    r = await client.post("/api/v1/submissions", headers=h, json={
        "question_id": qid, "language": lang, "code": code, "mode": mode, **kw})
    assert r.status_code == 202, r.text
    assert r.json()["verdict"]["status"] == "queued"  # returned before judging
    await jobs.drain()
    return (await client.get(f"/api/v1/submissions/{r.json()['id']}", headers=h)).json()


# ---------------- verdict aggregation (pure) ----------------


def test_status_mapping_and_priority():
    assert [map_status(i) for i in (3, 4, 5, 6, 11, 13)] == [
        "accepted", "wrong_answer", "time_limit_exceeded", "compilation_error",
        "runtime_error", "internal_error"]
    cases = [JCase("1", "1", True), JCase("2", "2", False), JCase("3", "3", False)]
    res = [CaseResult("accepted"), CaseResult("wrong_answer"), CaseResult("time_limit_exceeded")]
    o = aggregate(res, cases)
    assert o.verdict == "time_limit_exceeded" and o.passed == 1 and o.total == 3
    assert aggregate([CaseResult("accepted")] * 3, cases).verdict == "accepted"


# ---------------- pipeline ----------------


async def test_submit_accepted_updates_skill_graph(client):
    _, topic, q = await setup(client)
    h = await register(client)
    s = await submit(client, h, q["id"], time_taken_ms=60_000)
    v = s["verdict"]
    assert v["status"] == "accepted" and v["label"] == "Accepted" and v["judged_by"] == "judge0"
    assert v["details"]["passed"] == 3 and v["details"]["total"] == 3
    # hidden test inputs never leave the server
    assert "SECRET" not in str(s)
    hidden = [c for c in v["details"]["cases"] if not c["visible"]]
    assert len(hidden) == 2 and all("stdin" not in c for c in hidden)
    skills = (await client.get("/api/v1/me/skills", headers=h)).json()
    node = next(n for n in skills if n["name"] == "Math")
    assert node["attempt_count"] == 1 and node["mastery_score"] > 0
    # the fake judge received the hidden tests with expected outputs (Judge0 decides)
    call = client.judge.calls[-1]
    assert [c.expected for c in call["cases"]] == ["4", "14", "0"]


@pytest.mark.parametrize("code,status", [("#WA", "wrong_answer"),
                                         ("#TLE", "time_limit_exceeded"),
                                         ("#CE", "compilation_error")])
async def test_failing_verdicts(client, code, status):
    _, _, q = await setup(client)
    h = await register(client)
    s = await submit(client, h, q["id"], code=code)
    assert s["verdict"]["status"] == status and s["verdict"]["is_correct"] is False
    if status == "compilation_error":
        assert "expected ';'" in s["verdict"]["details"]["compile_output"]


async def test_run_uses_samples_or_custom_stdin_and_never_touches_mastery(client):
    _, _, q = await setup(client)
    h = await register(client)
    s = await submit(client, h, q["id"], code="#ECHO", mode="run", stdin="hello")
    case = s["verdict"]["details"]["cases"][0]
    assert case["stdout"] == "hello" and case["expected"] is None
    s = await submit(client, h, q["id"], code="#AC", mode="run")
    assert s["verdict"]["details"]["total"] == 1  # samples only, no hidden tests
    skills = (await client.get("/api/v1/me/skills", headers=h)).json()
    assert next(n for n in skills if n["name"] == "Math")["attempt_count"] == 0


async def test_judge_outage_is_recorded_not_guessed(client):
    _, _, q = await setup(client)
    h = await register(client)
    s = await submit(client, h, q["id"], code="#FAIL")
    assert s["verdict"]["status"] == "internal_error"
    assert "sandbox unreachable" in s["verdict"]["details"]["error"]
    skills = (await client.get("/api/v1/me/skills", headers=h)).json()
    assert next(n for n in skills if n["name"] == "Math")["attempt_count"] == 0


async def test_validation_privacy_and_inflight_limit(client):
    cm, _, q = await setup(client)
    h = await register(client)
    mcq = (await client.post("/api/v1/questions", headers=cm, json={
        "type": "mcq", "title": "Not code", "body": "x", "difficulty": "easy",
        "status": "published", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "answer": {"correct": ["a"]}})).json()
    bad = await client.post("/api/v1/submissions", headers=h, json={
        "question_id": mcq["id"], "language": "python", "code": "x"})
    assert bad.status_code == 422
    bad = await client.post("/api/v1/submissions", headers=h, json={
        "question_id": q["id"], "language": "python", "code": "x", "stdin": "1"})
    assert bad.status_code == 422  # stdin only for run
    first = await client.post("/api/v1/submissions", headers=h, json={
        "question_id": q["id"], "language": "python", "code": "#AC"})
    second = await client.post("/api/v1/submissions", headers=h, json={
        "question_id": q["id"], "language": "python", "code": "#AC"})
    assert second.status_code == 429  # one in-flight job per student
    await jobs.drain()
    other = await register(client, "other@t.dev")
    r = await client.get(f"/api/v1/submissions/{first.json()['id']}", headers=other)
    assert r.status_code == 404


async def test_sql_question_judged_against_reference_output(client):
    cm = await login(client, "content_manager@t.dev")
    q = (await client.post("/api/v1/questions", headers=cm, json={
        "type": "sql", "title": "Max salary", "body": "Highest salary", "difficulty": "easy",
        "status": "published",
        "meta": {"schema_sql": "CREATE TABLE e(s INT);", "seed_sql": "INSERT INTO e VALUES(5);"},
        "answer": {"reference_query": "SELECT MAX(s) FROM e;"}})).json()
    h = await register(client)
    s = await submit(client, h, q["id"], code="SELECT MAX(s) FROM e; -- #AC", lang="sql")
    assert s["verdict"]["status"] == "accepted"
    ref_call, user_call = client.judge.calls[-2:]
    assert "SELECT MAX(s) FROM e;" in ref_call["source"] and "INSERT" in ref_call["source"]
    assert user_call["cases"][0].expected == "ok"  # reference stdout becomes expected output


async def test_test_mode_coding_scored_after_judging(client):
    cm, _, q = await setup(client)
    t = (await client.post("/api/v1/tests", headers=cm, json={
        "title": "Code round", "is_published": True, "negative_marking": True,
        "negative_ratio": 0.5, "questions": [{"question_id": q["id"], "marks": 10}]})).json()
    h = await register(client)
    a = (await client.post(f"/api/v1/tests/{t['id']}/attempts", headers=h)).json()
    tq = a["items"][0]["tq_id"]
    await client.put(f"/api/v1/attempts/{a['id']}/answers/{tq}", headers=h,
                     json={"answer": {"code": "#WA", "language": "cpp"}})
    res = (await client.post(f"/api/v1/attempts/{a['id']}/submit", headers=h)).json()
    assert res["counts"]["pending"] == 1 and res["max_score"] == 0
    await jobs.drain()
    res = (await client.get(f"/api/v1/attempts/{a['id']}/analysis", headers=h)).json()
    item = res["items"][0]
    assert item["status"] == "incorrect" and item["verdict"] == "wrong_answer"
    assert res["score"] == -5 and res["max_score"] == 10
    assert client.judge.calls[-1]["language"] == "cpp"


# ---------------- readiness & analytics ----------------


async def test_readiness_report_matches_equation(client):
    _, _, q = await setup(client)
    h = await register(client)
    await submit(client, h, q["id"], time_taken_ms=30_000)
    r = (await client.get("/api/v1/me/readiness", headers=h)).json()
    comps = {c["key"]: c["value"] for c in r["components"]}
    assert r["overall"] == readiness(comps)
    interview = next(c for c in r["components"] if c["key"] == "interview")
    assert interview["value"] == 0 and interview["available"] is False
    assert comps["coding"] > 0 and comps["dsa"] > 0
    assert r["recommendation"]["title"]
    assert r["history"][-1]["overall"] == r["overall"]


async def test_company_weights_override_readiness(client):
    cm, _, q = await setup(client)
    c = (await client.post("/api/v1/companies", headers=cm, json={
        "name": "AptiCo",
        "skill_weights": {"dsa": 10, "oop": 10, "dbms": 10, "os": 10, "aptitude": 50, "hr": 10},
        "oa_pattern": {"coding_questions": 1, "mcqs": 30, "duration_minutes": 60,
                       "difficulty": "easy", "frequent_topics": []},
        "readiness_weights": {"dsa": 0.1, "csf": 0.1, "coding": 0.5, "aptitude": 0.1,
                              "interview": 0.1, "consistency": 0.1}})).json()
    h = await register(client)
    await submit(client, h, q["id"])
    generic = (await client.get("/api/v1/me/readiness", headers=h)).json()
    custom = (await client.get(f"/api/v1/me/readiness?company={c['slug']}", headers=h)).json()
    assert custom["custom_weights"] is True
    comps = {x["key"]: x["value"] for x in custom["components"]}
    assert custom["overall"] == readiness(comps, {"dsa": 0.1, "csf": 0.1, "coding": 0.5,
                                                  "aptitude": 0.1, "interview": 0.1,
                                                  "consistency": 0.1})
    assert custom["overall"] != generic["overall"]
    assert "not an official specification" in custom["company"]["pattern_disclaimer"]


async def test_analytics_derived_from_attempts(client):
    _, _, q = await setup(client)
    h = await register(client)
    await submit(client, h, q["id"], code="#WA", time_taken_ms=90_000)
    await submit(client, h, q["id"], code="#AC", time_taken_ms=40_000)
    await submit(client, h, q["id"], code="#AC", mode="run")  # runs never count
    a = (await client.get("/api/v1/me/analytics", headers=h)).json()
    today = a["accuracy_over_time"][-1]
    assert today["answered"] == 2 and today["correct"] == 1 and today["accuracy"] == 0.5
    medium = next(d for d in a["difficulty_distribution"] if d["difficulty"] == "medium")
    assert medium == {"difficulty": "medium", "attempted": 1, "correct": 1}
    assert [t["time_ms"] for t in a["time_per_question"]] == [90_000, 40_000]
    assert a["topic_mastery"][0]["topic"] == "Math"
    assert a["weakest_topics"][0]["topic"] == "Math"
    assert a["total_scored"] == 2


async def test_practised_subtree_not_reported_as_unpractised(client):
    cm = await login(client, "content_manager@t.dev")
    parent = (await client.post("/api/v1/topics", json={"name": "Dynamic Programming",
                                                        "area": "DSA"}, headers=cm)).json()
    child = (await client.post("/api/v1/topics", json={"name": "1D DP", "area": "DSA",
                                                       "parent_id": parent["id"]},
                               headers=cm)).json()
    q = (await client.post("/api/v1/questions", json={**CODING, "topic_id": child["id"]},
                           headers=cm)).json()
    c = (await client.post("/api/v1/companies", headers=cm, json={
        "name": "DPCo",
        "skill_weights": {"dsa": 60, "oop": 10, "dbms": 10, "os": 10, "aptitude": 5, "hr": 5},
        "oa_pattern": {"coding_questions": 2, "mcqs": 0, "duration_minutes": 60,
                       "difficulty": "medium", "frequent_topics": ["Dynamic Programming"]}})).json()
    h = await register(client)
    before = (await client.get(f"/api/v1/me/readiness?company={c['slug']}", headers=h)).json()
    assert "Dynamic Programming" in [w["name"] for w in before["weaknesses"]]
    await submit(client, h, q["id"], code="#WA")
    after = (await client.get(f"/api/v1/me/readiness?company={c['slug']}", headers=h)).json()
    names = [w["name"] for w in after["weaknesses"]]
    assert "Dynamic Programming" not in names and "1D DP" in names
