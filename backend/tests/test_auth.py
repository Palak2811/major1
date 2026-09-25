from app.core.security import hash_password, verify_password
from tests.conftest import login, register

REFRESH = "pp_refresh"


def test_argon2_hash_is_salted_and_verifies():
    a, b = hash_password("same-pass-1"), hash_password("same-pass-1")
    assert a != b and a.startswith("$argon2id$")
    assert verify_password("same-pass-1", a)
    assert not verify_password("wrong-pass-1", a)
    assert not verify_password("x", None)


async def test_register_then_me(client):
    h = await register(client)
    r = await client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 200
    assert r.json()["role"] == "student"
    assert r.json()["has_password"] is True


async def test_register_duplicate_and_weak_password(client):
    await register(client)
    r = await client.post("/api/v1/auth/register",
                          json={"email": "stu@t.dev", "password": "Passw0rd!xyz", "full_name": "X"})
    assert r.status_code == 409
    r = await client.post("/api/v1/auth/register",
                          json={"email": "new@t.dev", "password": "onlyletters", "full_name": "X"})
    assert r.status_code == 422


async def test_login_wrong_password_is_401(client):
    r = await client.post("/api/v1/auth/login",
                          json={"email": "admin@t.dev", "password": "nope-nope-1"})
    assert r.status_code == 401


async def test_refresh_rotates_and_detects_reuse(client):
    await register(client)
    first = client.cookies.get(REFRESH)
    assert first

    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    second = client.cookies.get(REFRESH)
    assert second and second != first

    # Replaying the rotated-out token revokes the whole family...
    client.cookies.set(REFRESH, first, path="/api/v1/auth")
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401
    # ...so even the latest token is now dead.
    client.cookies.clear()
    client.cookies.set(REFRESH, second, path="/api/v1/auth")
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


async def test_logout_revokes_refresh(client):
    await register(client)
    token = client.cookies.get(REFRESH)
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    client.cookies.set(REFRESH, token, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_google_mock_flow_creates_student(client):
    r = await client.get("/api/v1/auth/google/login")
    assert r.status_code == 302
    r = await client.get(r.headers["location"])
    assert r.status_code == 302 and r.headers["location"].endswith("/auth/callback")
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    assert r.json()["user"]["google_linked"] is True
    assert r.json()["user"]["role"] == "student"


async def test_google_callback_rejects_bad_state(client):
    await client.get("/api/v1/auth/google/login")
    r = await client.get("/api/v1/auth/google/callback?code=mock&state=forged")
    assert "error=oauth_state" in r.headers["location"]


async def test_rbac_401_vs_403(client):
    assert (await client.get("/api/v1/users")).status_code == 401
    student = await register(client)
    assert (await client.get("/api/v1/users", headers=student)).status_code == 403
    cm = await login(client, "content_manager@t.dev")
    assert (await client.get("/api/v1/users", headers=cm)).status_code == 403
    assert (await client.get("/api/v1/users/stats", headers=cm)).status_code == 200
    admin = await login(client, "admin@t.dev")
    assert (await client.get("/api/v1/users", headers=admin)).status_code == 200


async def test_role_change_applies_immediately(client):
    student = await register(client)
    admin = await login(client, "admin@t.dev")
    users = (await client.get("/api/v1/users?q=stu@", headers=admin)).json()["items"]
    r = await client.patch(f"/api/v1/users/{users[0]['id']}", json={"role": "content_manager"},
                           headers=admin)
    assert r.status_code == 200
    # Same (old) access token now has content scopes because scopes come from the DB role.
    r = await client.post("/api/v1/topics", json={"name": "Heaps", "area": "DSA"},
                          headers=student)
    assert r.status_code == 201


async def test_admin_cannot_demote_self(client):
    admin = await login(client, "admin@t.dev")
    me = (await client.get("/api/v1/auth/me", headers=admin)).json()
    r = await client.patch(f"/api/v1/users/{me['id']}", json={"role": "student"}, headers=admin)
    assert r.status_code == 400
