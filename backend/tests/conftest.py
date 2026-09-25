import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GEMINI_API_KEY"] = ""  # tests must never call the real LLM
os.environ["REDIS_URL"] = ""
os.environ["UPLOADS_DIR"] = os.path.join(os.path.dirname(__file__), ".uploads")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.db import get_db  # noqa: E402
from app.core.security import ROLE_SCOPES, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Profile, Role, User  # noqa: E402
from app.services import jobs, llm  # noqa: E402
from app.services.judge import ACCEPTED, CE, TLE, WRONG, CaseResult, set_judge  # noqa: E402


@pytest_asyncio.fixture
async def sessionmaker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool,
                                 connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        roles = {n: Role(name=n, scopes=s) for n, s in ROLE_SCOPES.items()}
        db.add_all(roles.values())
        for name in ("admin", "content_manager"):
            u = User(email=f"{name}@t.dev", full_name=name,
                     password_hash=hash_password("Passw0rd!xyz"), role=roles[name])
            u.profile = Profile()
            db.add(u)
        await db.commit()
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def client(sessionmaker):
    async def _db():
        async with sessionmaker() as s:
            yield s

    app.dependency_overrides[get_db] = _db
    jobs.session_factory = sessionmaker
    jobs.defer = True
    fake = FakeJudge()
    set_judge(fake)
    fake_llm = FakeLLM()
    llm.set_client(fake_llm)
    llm.reset_cache()
    llm._windows.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.judge = fake  # type: ignore[attr-defined]
        c.llm = fake_llm  # type: ignore[attr-defined]
        yield c
    await jobs.drain()
    set_judge(None)
    llm.set_client(None)
    app.dependency_overrides.clear()


class FakeLLM(llm.MockClient):
    """Scriptable LLM. `script[marker]` applies when `marker` occurs in the prompt; the value is
    a dict, a function(prompt) -> dict, or an Exception. Unscripted calls fall back to the
    schema-shaped mock. Embeddings: offline hashing."""

    def __init__(self):
        self.script: dict = {}
        self.calls: list[dict] = []

    async def generate(self, *, model, system, prompt, schema, temperature):
        task = next((t for t in self.script if t in prompt), None)
        self.calls.append({"model": model, "prompt": prompt, "task": task})
        if task is not None:
            out = self.script[task]
            if isinstance(out, Exception):
                raise out
            data = out(prompt) if callable(out) else out
            return llm.LLMResult(data, model, 100, 50)
        return await super().generate(model=model, system=system, prompt=prompt, schema=schema,
                                      temperature=temperature)


class FakeJudge:
    """Stands in for Judge0. The *code* carries a directive: '#AC', '#WA', '#TLE', '#CE',
    '#FAIL' (sandbox unreachable). '#ECHO' prints stdin. Records every call."""

    def __init__(self):
        self.calls = []

    async def execute(self, language, source, cases, time_limit_s, memory_limit_kb):
        self.calls.append({"language": language, "source": source, "cases": cases})
        if "#FAIL" in source:
            raise ConnectionError("sandbox unreachable")
        out = []
        for c in cases:
            if "#CE" in source:
                out.append(CaseResult(CE, compile_output="error: expected ';'"))
            elif "#TLE" in source:
                out.append(CaseResult(TLE, time_s=2.0))
            elif "#WA" in source and c.expected is not None:
                out.append(CaseResult(WRONG, stdout="nope", time_s=0.01, memory_kb=900))
            elif "#ECHO" in source:
                out.append(CaseResult(ACCEPTED, stdout=c.stdin, time_s=0.01, memory_kb=900))
            else:
                out.append(CaseResult(ACCEPTED, stdout=c.expected or "ok", time_s=0.02,
                                      memory_kb=1000))
        return out


async def login(client: AsyncClient, email: str, password: str = "Passw0rd!xyz") -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def register(client: AsyncClient, email: str = "stu@t.dev") -> dict:
    r = await client.post("/api/v1/auth/register",
                          json={"email": email, "password": "Passw0rd!xyz", "full_name": "Stu"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
