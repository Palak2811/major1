"""Judge0 client + verdict aggregation.

Submitted code is sent to the Judge0 sandbox over HTTP and never executed by this process.
Each test case goes to Judge0 with its `expected_output`, so **Judge0 itself decides**
Accepted / Wrong Answer / TLE / CE / RE. We only combine per-case verdicts into one.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.config import get_settings

LANGUAGES = {  # our key -> (Judge0 language_id, label)
    "python": (109, "Python 3.13"),
    "cpp": (105, "C++ (GCC 14)"),
    "java": (62, "Java 13"),
    "javascript": (102, "JavaScript (Node 22)"),
    "sql": (82, "SQL (SQLite 3)"),
}
CODE_LANGUAGES = ("python", "cpp", "java", "javascript")

ACCEPTED = "accepted"
WRONG = "wrong_answer"
TLE = "time_limit_exceeded"
CE = "compilation_error"
RE = "runtime_error"
INTERNAL = "internal_error"

VERDICT_LABEL = {ACCEPTED: "Accepted", WRONG: "Wrong Answer", TLE: "Time Limit Exceeded",
                 CE: "Compilation Error", RE: "Runtime Error", INTERNAL: "Judge error"}
# When cases disagree, the most fundamental failure is reported.
PRIORITY = [CE, RE, TLE, WRONG, INTERNAL, ACCEPTED]
MAX_CASES = 12


def map_status(status_id: int) -> str:
    if status_id == 3:
        return ACCEPTED
    if status_id == 4:
        return WRONG
    if status_id == 5:
        return TLE
    if status_id == 6:
        return CE
    if 7 <= status_id <= 12 or status_id == 14:
        return RE
    return INTERNAL  # 13 internal error, or anything unexpected


@dataclass
class Case:
    stdin: str
    expected: str | None  # None for free-form "run with custom input"
    visible: bool


@dataclass
class CaseResult:
    verdict: str
    stdout: str | None = None
    stderr: str | None = None
    compile_output: str | None = None
    time_s: float | None = None
    memory_kb: int | None = None
    message: str | None = None


@dataclass
class Outcome:
    verdict: str
    passed: int
    total: int
    cases: list[CaseResult] = field(default_factory=list)
    max_time_s: float | None = None
    max_memory_kb: int | None = None
    compile_output: str | None = None


def aggregate(results: list[CaseResult], cases: list[Case]) -> Outcome:
    graded = [r for r, c in zip(results, cases, strict=True) if c.expected is not None]
    if not results:
        return Outcome(INTERNAL, 0, 0)
    if graded:
        verdict = min((r.verdict for r in graded), key=PRIORITY.index)
    else:  # custom-input run: nothing to compare, report execution status only
        worst = min((r.verdict for r in results), key=PRIORITY.index)
        verdict = worst if worst != WRONG else ACCEPTED
    times = [r.time_s for r in results if r.time_s is not None]
    mems = [r.memory_kb for r in results if r.memory_kb is not None]
    return Outcome(
        verdict=verdict,
        passed=sum(r.verdict == ACCEPTED for r in graded),
        total=len(graded),
        cases=results,
        max_time_s=max(times) if times else None,
        max_memory_kb=max(mems) if mems else None,
        compile_output=next((r.compile_output for r in results if r.compile_output), None),
    )


class JudgeClient(Protocol):
    async def execute(self, language: str, source: str, cases: list[Case],
                      time_limit_s: float, memory_limit_kb: int) -> list[CaseResult]: ...


class Judge0Client:
    """Talks to a Judge0 CE instance (default: the free public ce.judge0.com)."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 poll_interval: float = 1.0, timeout_s: float = 90.0):
        s = get_settings()
        self.base = (base_url or s.judge0_url).rstrip("/")
        self.headers = {"content-type": "application/json"}
        key = api_key if api_key is not None else s.judge0_api_key
        if key:
            self.headers["X-Auth-Token"] = key
        self.poll_interval = poll_interval
        self.timeout_s = timeout_s

    async def execute(self, language, source, cases, time_limit_s, memory_limit_kb):
        lang_id = LANGUAGES[language][0]
        payload = {"submissions": [{
            "language_id": lang_id, "source_code": source, "stdin": c.stdin,
            **({"expected_output": c.expected} if c.expected is not None else {}),
            "cpu_time_limit": time_limit_s, "wall_time_limit": max(time_limit_s * 3, 5),
            "memory_limit": memory_limit_kb, "enable_network": False,
        } for c in cases]}
        async with httpx.AsyncClient(timeout=30, headers=self.headers) as http:
            r = await http.post(f"{self.base}/submissions/batch?base64_encoded=false", json=payload)
            r.raise_for_status()
            tokens = [t.get("token") for t in r.json()]
            if not all(tokens):
                raise RuntimeError(f"Judge0 rejected a submission: {r.text[:300]}")
            fields = "token,stdout,stderr,compile_output,message,status,time,memory"
            waited = 0.0
            while True:
                await asyncio.sleep(self.poll_interval)
                waited += self.poll_interval
                g = await http.get(f"{self.base}/submissions/batch", params={
                    "tokens": ",".join(tokens), "base64_encoded": "false", "fields": fields})
                g.raise_for_status()
                subs = g.json()["submissions"]
                if all(s["status"]["id"] not in (1, 2) for s in subs):
                    break
                if waited >= self.timeout_s:
                    raise TimeoutError("Judge0 did not finish in time")
        return [CaseResult(
            verdict=map_status(s["status"]["id"]), stdout=s.get("stdout"),
            stderr=s.get("stderr"), compile_output=s.get("compile_output"),
            message=s.get("message"),
            time_s=float(s["time"]) if s.get("time") else None, memory_kb=s.get("memory"),
        ) for s in subs]


_client: JudgeClient | None = None


def get_judge() -> JudgeClient:
    global _client
    if _client is None:
        _client = Judge0Client()
    return _client


def set_judge(client: JudgeClient | None) -> None:
    """Swap the client (tests use an in-memory fake)."""
    global _client
    _client = client
