import pytest
from pydantic import ValidationError

from app.schemas import PATTERN_DISCLAIMER, QuestionIn
from tests.conftest import login, register

COMPANY = {
    "name": "Acme Corp",
    "skill_weights": {"dsa": 40, "oop": 10, "dbms": 10, "os": 10, "aptitude": 20, "hr": 10},
    "oa_pattern": {"coding_questions": 2, "mcqs": 20, "duration_minutes": 90,
                   "difficulty": "medium", "frequent_topics": ["Graphs"]},
}

MCQ = {
    "type": "mcq", "title": "Stack order", "body": "Stack is?", "difficulty": "easy",
    "options": [{"id": "a", "text": "LIFO"}, {"id": "b", "text": "FIFO"}],
    "answer": {"correct": ["a"]}, "explanation": "Last in, first out.", "status": "published",
}


def test_question_type_contracts():
    QuestionIn.model_validate(MCQ)
    with pytest.raises(ValidationError):
        QuestionIn.model_validate({**MCQ, "answer": {"correct": ["a", "b"]}})  # mcq needs one
    with pytest.raises(ValidationError):
        QuestionIn.model_validate({**MCQ, "answer": {"correct": ["z"]}})
    with pytest.raises(ValidationError):  # coding without samples/constraints
        QuestionIn.model_validate({**MCQ, "type": "coding", "options": [], "answer": {}})
    with pytest.raises(ValidationError):  # numerical needs a number
        QuestionIn.model_validate({**MCQ, "type": "numerical", "options": [],
                                   "answer": {"value": "six"}})
    QuestionIn.model_validate({**MCQ, "type": "numerical", "options": [],
                               "answer": {"value": 6, "tolerance": 0.5}})


async def test_admin_flow_topic_question_company(client):
    cm = await login(client, "content_manager@t.dev")

    r = await client.post("/api/v1/companies", json=COMPANY, headers=cm)
    assert r.status_code == 201, r.text
    company = r.json()
    assert company["slug"] == "acme-corp"
    assert company["pattern_disclaimer"] == PATTERN_DISCLAIMER

    r = await client.post("/api/v1/topics", json={"name": "Stacks", "area": "DSA"}, headers=cm)
    assert r.status_code == 201
    topic = r.json()

    r = await client.post("/api/v1/questions", headers=cm,
                          json={**MCQ, "topic_id": topic["id"], "company_ids": [company["id"]]})
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["topic"]["slug"] == "stacks"
    assert q["companies"][0]["name"] == "Acme Corp"
    assert q["answer"] == {"correct": ["a"]}

    # Student sees it, without the answer, and the company shows the disclaimer
    student = await register(client)
    r = await client.get(f"/api/v1/questions?company_id={company['id']}", headers=student)
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["answer"] is None and items[0]["explanation"] is None
    r = await client.get("/api/v1/companies/acme-corp", headers=student)
    assert r.json()["question_count"] == 1
    assert "not an official specification" in r.json()["pattern_disclaimer"]

    # Students cannot write
    r = await client.post("/api/v1/companies", json={**COMPANY, "name": "X"}, headers=student)
    assert r.status_code == 403


async def test_students_never_see_drafts(client):
    cm = await login(client, "content_manager@t.dev")
    r = await client.post("/api/v1/questions", json={**MCQ, "status": "draft"}, headers=cm)
    qid = r.json()["id"]
    student = await register(client)
    r = await client.get("/api/v1/questions?status=draft", headers=student)
    assert r.json()["total"] == 0
    assert (await client.get(f"/api/v1/questions/{qid}", headers=student)).status_code == 404


async def test_question_patch_revalidates(client):
    cm = await login(client, "content_manager@t.dev")
    qid = (await client.post("/api/v1/questions", json=MCQ, headers=cm)).json()["id"]
    r = await client.patch(f"/api/v1/questions/{qid}", json={"type": "multi_select",
                           "answer": {"correct": ["a", "b"]}}, headers=cm)
    assert r.status_code == 200 and r.json()["type"] == "multi_select"
    r = await client.patch(f"/api/v1/questions/{qid}", json={"type": "numerical"}, headers=cm)
    assert r.status_code == 422


async def test_company_weight_validation(client):
    cm = await login(client, "content_manager@t.dev")
    bad = {**COMPANY, "skill_weights": {**COMPANY["skill_weights"], "dsa": 90}}
    assert (await client.post("/api/v1/companies", json=bad, headers=cm)).status_code == 422
    bad_rw = {**COMPANY, "readiness_weights": {"dsa": 0.5, "csf": 0.5, "coding": 0.5,
              "aptitude": 0, "interview": 0, "consistency": 0}}
    assert (await client.post("/api/v1/companies", json=bad_rw, headers=cm)).status_code == 422


async def test_topic_cycle_rejected(client):
    cm = await login(client, "content_manager@t.dev")
    a = (await client.post("/api/v1/topics", json={"name": "A", "area": "DSA"}, headers=cm)).json()
    b = (await client.post("/api/v1/topics", json={"name": "B", "area": "DSA",
                                                   "parent_id": a["id"]}, headers=cm)).json()
    r = await client.patch(f"/api/v1/topics/{a['id']}", json={"parent_id": b["id"]}, headers=cm)
    assert r.status_code == 422


async def test_profile_update(client):
    cm = await login(client, "content_manager@t.dev")
    cid = (await client.post("/api/v1/companies", json=COMPANY, headers=cm)).json()["id"]
    student = await register(client)
    r = await client.put("/api/v1/users/me/profile", headers=student, json={
        "college": "NIT", "branch": "CSE", "graduation_year": 2027, "target_role": "SDE",
        "target_company_ids": [cid], "preferred_language": "cpp"})
    assert r.status_code == 200
    body = r.json()
    assert body["completeness"] == 100 and body["dsa_score"] is None
    r = await client.put("/api/v1/users/me/profile", headers=student,
                         json={"target_company_ids": [9999]})
    assert r.status_code == 422
