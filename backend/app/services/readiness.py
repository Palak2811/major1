"""Company Readiness Score — Equation 3.1. Pure and deterministic; no LLM involvement.

    readiness = 0.25·DSA + 0.20·CSF + 0.20·Coding + 0.15·Aptitude + 0.10·Interview
              + 0.10·Consistency

Every component is normalised to [0, 100]. A company profile may override the weights
(they must still sum to 1). Components with no evidence score 0 and are flagged as such;
they are never estimated.
"""

from dataclasses import dataclass

COMPONENTS = ("dsa", "csf", "coding", "aptitude", "interview", "consistency")
DEFAULT_WEIGHTS: dict[str, float] = {"dsa": 0.25, "csf": 0.20, "coding": 0.20, "aptitude": 0.15,
                                     "interview": 0.10, "consistency": 0.10}
LABELS = {"dsa": "DSA", "csf": "CS fundamentals", "coding": "Coding performance",
          "aptitude": "Aptitude", "interview": "Interview performance",
          "consistency": "Consistency"}

CONSISTENCY_WINDOW_DAYS = 14
STREAK_TARGET_DAYS = 14


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def validate_weights(w: dict[str, float]) -> dict[str, float]:
    if set(w) != set(COMPONENTS):
        raise ValueError(f"weights must have exactly {COMPONENTS}")
    if any(v < 0 for v in w.values()) or abs(sum(w.values()) - 1) > 1e-6:
        raise ValueError("weights must be non-negative and sum to 1")
    return w


def readiness(components: dict[str, float], weights: dict[str, float] | None = None) -> float:
    """Equation 3.1: weighted sum of [0, 100] components, rounded to 2 dp."""
    w = validate_weights(weights or DEFAULT_WEIGHTS)
    missing = set(COMPONENTS) - set(components)
    if missing:
        raise ValueError(f"missing components: {sorted(missing)}")
    return round(sum(w[k] * _clamp(components[k]) for k in COMPONENTS), 2)


def contributions(components: dict[str, float], weights: dict[str, float]) -> dict[str, float]:
    return {k: round(weights[k] * _clamp(components[k]), 2) for k in COMPONENTS}


# ---------------- component formulas ----------------


def dsa_component(dsa_mastery: float | None, dsa_coding_accept_ratio: float | None) -> float:
    """Skill-graph DSA mastery, blended 70/30 with the accepted ratio of DSA coding problems."""
    if dsa_mastery is None and dsa_coding_accept_ratio is None:
        return 0.0
    if dsa_coding_accept_ratio is None:
        return _clamp(dsa_mastery or 0.0)
    if dsa_mastery is None:
        return _clamp(100 * dsa_coding_accept_ratio)
    return _clamp(0.7 * dsa_mastery + 0.3 * 100 * dsa_coding_accept_ratio)


def coding_component(problems_attempted: int, problems_accepted: int,
                     speed_scores: list[float]) -> float:
    """70% accepted ratio (distinct problems) + 30% mean solve speed of accepted submissions.

    speed score per accepted problem = min(1, expected_time / actual_time).
    """
    if problems_attempted == 0:
        return 0.0
    ratio = problems_accepted / problems_attempted
    speed = sum(speed_scores) / len(speed_scores) if speed_scores else 0.0
    return _clamp(70 * ratio + 30 * _clamp(speed, 0, 1))


def accuracy_component(correct: int, answered: int) -> float:
    return 0.0 if answered == 0 else _clamp(100 * correct / answered)


def consistency_component(streak_days: int, active_days_in_window: int) -> float:
    """Half current streak (capped at 14 days), half share of active days in the last 14."""
    streak = min(streak_days, STREAK_TARGET_DAYS) / STREAK_TARGET_DAYS
    regular = min(active_days_in_window, CONSISTENCY_WINDOW_DAYS) / CONSISTENCY_WINDOW_DAYS
    return _clamp(50 * streak + 50 * regular)


@dataclass(frozen=True)
class Weakness:
    name: str
    area: str
    mastery: float | None
    priority: float
    reason: str


def rank_weaknesses(nodes: list[tuple[str, str, float | None, int]],
                    area_emphasis: dict[str, float], frequent: set[str],
                    limit: int = 5) -> list[Weakness]:
    """Order leaf topics by how much closing the gap matters *for this company*.

    nodes: (topic name, area, mastery or None if never practised, attempts)
    priority = company area emphasis × (100 − mastery), +25% if the company frequently tests it.
    """
    out = []
    for name, area, mastery, attempts in nodes:
        emphasis = area_emphasis.get(area, 0.0)
        if emphasis <= 0:
            continue
        gap = 100 - (mastery or 0.0)
        boost = 1.25 if name in frequent else 1.0
        if attempts == 0 and name not in frequent:
            continue  # only surface unpractised topics the company is known to test
        reason = ("frequently tested, not practised yet" if attempts == 0
                  else f"mastery {round(mastery or 0)} in a {round(emphasis)}%-weighted area")
        out.append(Weakness(name, area, mastery, round(emphasis * gap * boost / 100, 2), reason))
    return sorted(out, key=lambda w: -w.priority)[:limit]
