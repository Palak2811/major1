"""Deterministic answer grading for non-code question types.

coding and sql are *not* graded here: executing them requires the Judge0 sandbox (Phase 3),
and submitted code must never run inside the backend process.
"""

import re
from dataclasses import dataclass

AUTO_TYPES = {"mcq", "multi_select", "numerical", "output_prediction"}
HEURISTIC_TYPES = {"debugging", "theory"}
SANDBOX_TYPES = {"coding", "sql"}


@dataclass(frozen=True)
class GradeResult:
    gradable: bool
    correct: bool
    score: float  # fraction in [0, 1]
    judged_by: str  # auto | heuristic | pending
    feedback: str = ""


PENDING = GradeResult(False, False, 0.0, "pending",
                      "Awaiting sandboxed execution (Judge0, Phase 3); not scored yet.")


def _norm_output(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.strip().splitlines())


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9+#]+", s.lower()) if len(w) > 3}


def is_answered(qtype: str, answer: dict | None) -> bool:
    if not answer:
        return False
    if qtype in ("mcq", "multi_select"):
        return bool(answer.get("selected"))
    if qtype == "numerical":
        return isinstance(answer.get("value"), (int, float))
    if qtype == "coding":
        return bool((answer.get("code") or "").strip())
    return bool((answer.get("text") or "").strip())


def grade(qtype: str, key: dict, answer: dict | None) -> GradeResult:
    if qtype in SANDBOX_TYPES:
        return PENDING
    if not is_answered(qtype, answer):
        return GradeResult(True, False, 0.0, "auto", "Not answered.")
    assert answer is not None

    if qtype in ("mcq", "multi_select"):
        ok = set(answer["selected"]) == set(key.get("correct", []))
        return GradeResult(True, ok, float(ok), "auto")

    if qtype == "numerical":
        ok = abs(float(answer["value"]) - float(key["value"])) <= float(key.get("tolerance", 0))
        return GradeResult(True, ok, float(ok), "auto")

    if qtype == "output_prediction":
        ok = _norm_output(answer["text"]) == _norm_output(key.get("expected_output", ""))
        return GradeResult(True, ok, float(ok), "auto")

    if qtype == "debugging":
        fix = _squash(key.get("fix", ""))
        if not fix:
            return PENDING
        ok = fix in _squash(answer["text"])
        return GradeResult(True, ok, float(ok), "heuristic",
                           "Checked by matching the expected fix; phrasing may differ.")

    if qtype == "theory":
        points = [p for p in key.get("key_points", []) if p.strip()]
        if not points:
            return GradeResult(False, False, 0.0, "pending", "No rubric; needs AI evaluation.")
        said = _words(answer["text"])
        covered = 0
        for p in points:
            pw = _words(p)
            if pw and len(pw & said) / len(pw) >= 0.5:
                covered += 1
        score = covered / len(points)
        return GradeResult(True, score >= 0.6, round(score, 3), "heuristic",
                           f"Covered {covered}/{len(points)} key points (keyword heuristic; "
                           "AI evaluation arrives in Phase 4).")

    return PENDING
