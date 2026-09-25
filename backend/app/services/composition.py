"""Pure helpers for test composition and streaks."""

import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

DEFAULT_MIX = {"easy": 0.3, "medium": 0.5, "hard": 0.2}
NEIGHBOURS = {"easy": ["medium", "hard"], "medium": ["easy", "hard"], "hard": ["medium", "easy"]}


@dataclass(frozen=True)
class Candidate:
    id: int
    difficulty: str
    topic_id: int | None


def quotas(n: int, mix: dict[str, float]) -> dict[str, int]:
    """Largest-remainder apportionment so quotas always sum to n."""
    total = sum(mix.values()) or 1
    raw = {k: n * v / total for k, v in mix.items()}
    q = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - q[k], reverse=True)[: n - sum(q.values())]:
        q[k] += 1
    return q


def balance(pool: list[Candidate], n: int, mix: dict[str, float] | None,
            rng: random.Random) -> list[Candidate]:
    """Pick n questions matching a difficulty mix, spreading across topics.

    Within a difficulty bucket, topics are taken round-robin so one topic can't dominate.
    Shortfalls in a bucket are filled from the nearest difficulty.
    """
    mix = mix or DEFAULT_MIX
    by_diff: dict[str, dict[int | None, list[Candidate]]] = defaultdict(lambda: defaultdict(list))
    for c in pool:
        by_diff[c.difficulty][c.topic_id].append(c)
    for topics in by_diff.values():
        for lst in topics.values():
            rng.shuffle(lst)

    def take(diff: str, k: int) -> list[Candidate]:
        topics = by_diff.get(diff, {})
        keys = list(topics)
        rng.shuffle(keys)
        out: list[Candidate] = []
        while len(out) < k and any(topics[t] for t in keys):
            for t in keys:
                if topics[t] and len(out) < k:
                    out.append(topics[t].pop())
        return out

    chosen: list[Candidate] = []
    for diff, k in quotas(min(n, len(pool)), mix).items():
        got = take(diff, k)
        for nb in NEIGHBOURS.get(diff, []):
            if len(got) >= k:
                break
            got += take(nb, k - len(got))
        chosen += got
    return chosen


def next_streak(last_active: date | None, today: date, current: int) -> int:
    if last_active == today:
        return max(current, 1)
    if last_active == today - timedelta(days=1):
        return current + 1
    return 1
