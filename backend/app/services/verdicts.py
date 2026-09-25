"""Verdict status vocabulary shared by grading, judging and analytics."""

CORRECT = frozenset({"correct", "accepted"})
INCORRECT = frozenset({"incorrect", "wrong_answer", "time_limit_exceeded", "compilation_error",
                       "runtime_error"})
PENDING = frozenset({"pending", "queued", "running", "internal_error"})
SCORED = CORRECT | INCORRECT


def outcome(status: str | None) -> str:
    """Collapse any verdict status to correct | incorrect | pending | unanswered."""
    if status is None or status == "unanswered":
        return "unanswered"
    if status in CORRECT:
        return "correct"
    if status in INCORRECT:
        return "incorrect"
    return "pending"
