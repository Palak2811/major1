"""LLM + embeddings client (Google Gemini) with the Phase 4 cost & reliability controls.

- Structured output only: every call passes a JSON Schema (from a Pydantic model) as the
  response contract, and the reply is re-validated with Pydantic. Free text never leaves here.
- Model routing: cheap model for simple tasks, stronger model for evaluation/interview/review.
- Response cache (Redis if configured, else in-process TTL cache).
- Per-user rate limit and daily token budget.
- Every call is traced to `ai_traces` (latency, tokens, estimated cost, success/failure).
- No GEMINI_API_KEY → a deterministic, clearly-labelled mock (so the app runs end-to-end).
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AITrace
from app.models.base import utcnow

GEMINI = "https://generativelanguage.googleapis.com/v1beta/models"
log = logging.getLogger(__name__)

# Tasks routed to the stronger model (the rest use the fast/cheap model).
STRONG_TASKS = {"evaluate", "interviewer", "code_review", "generate_question", "parse_resume",
                "parse_jd"}

# USD per 1M tokens (list prices; the free tier is actually billed at 0). Used for estimates.
PRICE = {"fast": (0.10, 0.40), "strong": (0.30, 2.50), "embed": (0.15, 0.0)}


class AIError(Exception):
    """Raised for anything the caller should show as 'AI unavailable' (never a fake answer)."""


class BudgetExceeded(AIError):
    pass


class TransientAIError(AIError):
    """Provider overloaded / rate-limited / timed out — worth a retry or another model."""


# ---------------- schema helpers ----------------


def json_schema(model: type[BaseModel]) -> dict:
    """Pydantic JSON schema with $refs inlined and titles dropped (Gemini-friendly)."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def walk(node: Any, is_properties: bool = False) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            if is_properties:  # keys here are field names (a field may be called "title")
                return {k: walk(v) for k, v in node.items()}
            return {k: walk(v, is_properties=(k == "properties")) for k, v in node.items()
                    if k not in ("title", "default")}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(raw)


# ---------------- clients ----------------


@dataclass
class LLMResult:
    data: dict
    model: str
    prompt_tokens: int
    completion_tokens: int
    mock: bool = False


class LLMClient(Protocol):
    async def generate(self, *, model: str, system: str, prompt: str, schema: dict,
                       temperature: float) -> LLMResult: ...

    async def embed(self, texts: list[str], task: str) -> list[list[float]]: ...


class GeminiClient:
    def __init__(self, api_key: str):
        self.key = api_key

    async def generate(self, *, model, system, prompt, schema, temperature):
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature,
                                 "responseMimeType": "application/json",
                                 "responseJsonSchema": schema},
        }
        try:
            async with httpx.AsyncClient(timeout=60) as http:
                r = await http.post(f"{GEMINI}/{model}:generateContent", json=body,
                                    headers={"x-goog-api-key": self.key})
        except httpx.TimeoutException as e:
            raise TransientAIError(f"Gemini timeout: {e}") from None
        if r.status_code in (429, 500, 502, 503, 504):
            raise TransientAIError(f"Gemini HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code != 200:
            raise AIError(f"Gemini HTTP {r.status_code}: {r.text[:200]}")
        d = r.json()
        try:
            text = d["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise AIError(f"Malformed model response: {e}") from None
        usage = d.get("usageMetadata", {})
        return LLMResult(data, d.get("modelVersion", model), usage.get("promptTokenCount", 0),
                         usage.get("candidatesTokenCount", 0))

    async def embed(self, texts, task):
        s = get_settings()
        out: list[list[float]] = []
        async with httpx.AsyncClient(timeout=60) as http:
            for i in range(0, len(texts), 64):
                batch = texts[i:i + 64]
                r = await http.post(
                    f"{GEMINI}/{s.embedding_model}:batchEmbedContents",
                    headers={"x-goog-api-key": self.key},
                    json={"requests": [{"model": f"models/{s.embedding_model}",
                                        "content": {"parts": [{"text": t}]}, "taskType": task,
                                        "outputDimensionality": s.embedding_dim} for t in batch]})
                if r.status_code != 200:
                    raise AIError(f"Embedding HTTP {r.status_code}: {r.text[:200]}")
                out += [e["values"] for e in r.json()["embeddings"]]
        return out


class MockClient:
    """Deterministic stand-in when no API key is configured. Output is always labelled mock."""

    async def generate(self, *, model, system, prompt, schema, temperature):
        return LLMResult(_mock_from_schema(schema, prompt), "mock", 0, 0, mock=True)

    async def embed(self, texts, task):
        return [_hash_embedding(t) for t in texts]


def _hash_embedding(text: str, dim: int | None = None) -> list[float]:
    """Bag-of-words hashing embedding: crude but semantic-ish, deterministic, offline."""
    dim = dim or get_settings().embedding_dim
    v = [0.0] * dim
    for w in text.lower().split():
        w = "".join(ch for ch in w if ch.isalnum())
        if len(w) > 2:
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % dim] += 1.0
    n = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / n for x in v]


def _mock_from_schema(schema: dict, prompt: str) -> dict:
    """Builds a schema-valid object; string fields say they are mock output."""
    ids = [p.split("]")[0] for p in prompt.split("[S")[1:]]
    first_source = f"S{ids[0]}" if ids else None

    def make(node: dict, name: str = "") -> Any:
        t = node.get("type")
        if isinstance(t, list):
            t = next((x for x in t if x != "null"), "null")
        if "enum" in node:
            return node["enum"][0]
        if t == "object":
            return {k: make(v, k) for k, v in node.get("properties", {}).items()}
        if t == "array":
            n = max(node.get("minItems", 1), 1)
            if name == "citations":
                return [first_source] if first_source else []
            return [make(node.get("items", {"type": "string"}), name) for _ in range(n)]
        if t == "integer":
            return max(node.get("minimum", 0), 5 if name == "score" else 0)
        if t == "number":
            return float(node.get("minimum", 0))
        if t == "boolean":
            return name in ("grounded", "agrees_with_verdict")
        return f"[mock AI — set GEMINI_API_KEY for real output] {name}"

    return make(schema)


_client: LLMClient | None = None


def get_client() -> LLMClient:
    global _client
    if _client is None:
        key = get_settings().gemini_api_key
        _client = GeminiClient(key) if key else MockClient()
    return _client


def set_client(c: LLMClient | None) -> None:
    global _client
    _client = c


def is_mock() -> bool:
    return isinstance(get_client(), MockClient)


# ---------------- cache ----------------


class _TTLCache:
    def __init__(self, max_items: int = 2000):
        self.data: dict[str, tuple[float, str]] = {}
        self.max = max_items

    async def get(self, k: str) -> str | None:
        hit = self.data.get(k)
        if hit and hit[0] > time.time():
            return hit[1]
        self.data.pop(k, None)
        return None

    async def set(self, k: str, v: str, ttl: int) -> None:
        if len(self.data) >= self.max:
            self.data.pop(next(iter(self.data)))
        self.data[k] = (time.time() + ttl, v)


class _RedisCache:
    def __init__(self, url: str):
        import redis.asyncio as redis

        self.r = redis.from_url(url)

    async def get(self, k):
        try:
            v = await self.r.get(k)
            return v.decode() if v else None
        except Exception:
            return None

    async def set(self, k, v, ttl):
        try:
            await self.r.set(k, v, ex=ttl)
        except Exception:
            pass


_cache = None


def cache():
    global _cache
    if _cache is None:
        url = get_settings().redis_url
        _cache = _RedisCache(url) if url else _TTLCache()
    return _cache


def reset_cache() -> None:
    global _cache
    _cache = None


# ---------------- limits ----------------

_windows: dict[int, deque] = {}


def check_rate(user_id: int) -> None:
    """Per-user sliding-window limit on AI calls (in-process; Redis-backed in Phase 5)."""
    limit = get_settings().ai_requests_per_minute
    now = time.time()
    q = _windows.setdefault(user_id, deque())
    while q and q[0] < now - 60:
        q.popleft()
    if len(q) >= limit:
        raise AIError(f"AI rate limit reached ({limit}/min) — try again shortly")
    q.append(now)


async def tokens_used_today(db: AsyncSession, user_id: int) -> int:
    start = datetime.combine(utcnow().date(), datetime.min.time(), tzinfo=utcnow().tzinfo)
    return await db.scalar(select(func.coalesce(
        func.sum(AITrace.prompt_tokens + AITrace.completion_tokens), 0)).where(
        AITrace.user_id == user_id, AITrace.created_at >= start)) or 0


# ---------------- the one entry point ----------------


async def structured(db: AsyncSession, *, user_id: int | None, task: str, system: str,
                     prompt: str, output: type[BaseModel], cache_key: str | None = None,
                     temperature: float = 0.3, meta: dict | None = None,
                     count_rate: bool = True) -> tuple[BaseModel, dict]:
    """Call the LLM with a schema contract; returns (validated model, trace info).

    Raises AIError on budget/rate/transport/schema failures — callers must surface that as
    'unavailable', never substitute an unvalidated answer.
    """
    s = get_settings()
    tier = "strong" if task in STRONG_TASKS else "fast"
    model = s.llm_model_strong if tier == "strong" else s.llm_model_fast
    ck = None
    if cache_key:
        ck = "ai:" + hashlib.sha256(f"{task}|{model}|{cache_key}".encode()).hexdigest()
        hit = await cache().get(ck)
        if hit:
            payload = json.loads(hit)
            await _trace(db, user_id, task, payload["model"], 0, 0, 0, True, None,
                         {**(meta or {}), "cache": "hit"})
            return output.model_validate(payload["data"]), {"model": payload["model"],
                                                              "cached": True,
                                                              "mock": payload["mock"]}
    if user_id is not None:
        if count_rate:
            check_rate(user_id)
        if await tokens_used_today(db, user_id) >= s.ai_daily_token_budget:
            raise BudgetExceeded("Daily AI token budget reached — resets at 00:00 UTC")

    client = get_client()
    other = s.llm_model_fast if tier == "strong" else s.llm_model_strong
    # Reliability: one backoff retry on the routed model, then fall back to the other tier.
    plan = [(model, 0.0), (model, 1.5), (other, 0.0)]
    res = None
    for i, (m, delay) in enumerate(plan):
        if delay:
            await asyncio.sleep(delay)
        started = time.perf_counter()
        try:
            res = await client.generate(model=m, system=system, prompt=prompt,
                                        schema=json_schema(output), temperature=temperature)
            parsed = output.model_validate(res.data)  # schema validation: the output contract
            if m != model:
                meta = {**(meta or {}), "fallback_from": model}
            break
        except TransientAIError as e:
            await _trace(db, user_id, task, m, 0, 0, int((time.perf_counter() - started) * 1000),
                         False, f"{type(e).__name__}: {e}", {**(meta or {}), "attempt": i + 1})
            if i == len(plan) - 1:
                msg = "The AI provider is overloaded right now — try again shortly"
                raise AIError(msg) from e
        except (AIError, ValidationError, httpx.HTTPError) as e:
            ms = int((time.perf_counter() - started) * 1000)
            await _trace(db, user_id, task, m, 0, 0, ms, False, f"{type(e).__name__}: {e}",
                         meta)
            msg = "The AI response failed validation or the provider was unreachable"
            raise AIError(msg) from e
    ms = int((time.perf_counter() - started) * 1000)
    await _trace(db, user_id, task, res.model, res.prompt_tokens, res.completion_tokens, ms,
                 True, None, {**(meta or {}), "tier": tier, "mock": res.mock})
    if ck:
        await cache().set(ck, json.dumps({"data": parsed.model_dump(), "model": res.model,
                                          "mock": res.mock}), s.ai_cache_ttl_seconds)
    return parsed, {"model": res.model, "cached": False, "mock": res.mock}


async def embed(db: AsyncSession, texts: list[str], task: str = "RETRIEVAL_DOCUMENT",
                user_id: int | None = None) -> list[list[float]]:
    started = time.perf_counter()
    try:
        vecs = await get_client().embed(texts, task)
    except (AIError, httpx.HTTPError) as e:
        await _trace(db, user_id, "embed", get_settings().embedding_model, 0, 0,
                     int((time.perf_counter() - started) * 1000), False, str(e)[:300], {})
        raise AIError("Embedding provider unreachable") from e
    approx_tokens = sum(len(t) // 4 for t in texts)
    await _trace(db, user_id, "embed", get_settings().embedding_model, approx_tokens, 0,
                 int((time.perf_counter() - started) * 1000), True, None,
                 {"count": len(texts), "tier": "embed"})
    return vecs


async def _trace(db: AsyncSession, user_id, task, model, pt, ct, ms, ok, err, meta) -> None:
    """Record the call in its own short transaction.

    Never on the request's session: that would hold a write lock for the whole LLM round-trip
    (deadlocking concurrent requests on SQLite) and the trace would be lost if the request
    later failed.
    """
    from app.services import jobs

    tier = (meta or {}).get("tier", "strong" if task in STRONG_TASKS else "fast")
    pin, pout = PRICE.get(tier, PRICE["fast"])
    rec = AITrace(user_id=user_id, call_type=task, model=model or "", prompt_tokens=pt,
                  completion_tokens=ct, latency_ms=ms, success=ok, error=err,
                  cost_usd=round((pt * pin + ct * pout) / 1_000_000, 6), meta=meta or {})
    try:
        async with jobs.session_factory() as s:
            s.add(rec)
            await s.commit()
    except Exception:  # observability must never break the user-facing call
        log.exception("failed to record AI trace")


def since(days: int) -> datetime:
    return utcnow() - timedelta(days=days)
