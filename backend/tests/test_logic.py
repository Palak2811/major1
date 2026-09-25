"""Unit tests for pure Phase 2 logic: mastery, grading, composition, streaks."""

import random
from datetime import UTC, date, datetime

import pytest

from app.services.composition import Candidate, balance, next_streak, quotas
from app.services.grading import grade
from app.services.mastery import (
    MAX_STEP,
    Evidence,
    SkillState,
    target_difficulty,
    update_mastery,
)

T = datetime(2026, 9, 25, tzinfo=UTC)


def ev(correct, difficulty="medium", **kw):
    return Evidence(correct=correct, difficulty=difficulty, at=T, **kw)


# ---------------- mastery ----------------


def test_graph_sequence_moves_up_bounded_and_monotonic():
    """A run of correct Graphs answers raises mastery steadily, never past 100 or by > MAX_STEP."""
    s = SkillState()
    history = [s.mastery_score]
    for _ in range(25):
        s = update_mastery(s, ev(True, time_ms=60_000))
        history.append(s.mastery_score)
    steps = [b - a for a, b in zip(history, history[1:], strict=False)]
    assert all(0 < d <= MAX_STEP for d in steps)
    assert 85 < s.mastery_score <= 100
    assert s.attempt_count == 25 and s.accuracy == 1.0 and s.last_attempt == T


def test_wrong_answers_move_down_and_floor_at_zero():
    s = SkillState(mastery_score=60, attempt_count=10, correct_count=6)
    for _ in range(30):
        prev = s.mastery_score
        s = update_mastery(s, ev(False))
        assert s.mastery_score <= prev
        assert prev - s.mastery_score <= MAX_STEP
    assert s.mastery_score == pytest.approx(0, abs=1)
    assert s.mastery_score >= 0


def test_mixed_sequence_net_direction():
    s = SkillState()
    for correct in [True, False, True, True, False, True, True, True]:
        s = update_mastery(s, ev(correct))
    assert s.mastery_score > 0 and s.accuracy == 0.75


def test_hard_correct_gains_more_than_easy_correct():
    base = SkillState(mastery_score=40, attempt_count=5)
    hard = update_mastery(base, ev(True, "hard"))
    easy = update_mastery(base, ev(True, "easy"))
    assert hard.mastery_score > easy.mastery_score > base.mastery_score


def test_missing_easy_hurts_more_than_missing_hard():
    base = SkillState(mastery_score=60, attempt_count=5)
    assert update_mastery(base, ev(False, "easy")).mastery_score < \
        update_mastery(base, ev(False, "hard")).mastery_score


def test_confident_wrong_penalised_more_than_unsure_wrong():
    base = SkillState(mastery_score=60, attempt_count=5)
    confident = update_mastery(base, ev(False, confidence=5))
    unsure = update_mastery(base, ev(False, confidence=1))
    assert confident.mastery_score < unsure.mastery_score


def test_low_confidence_correct_gains_less():
    base = SkillState(mastery_score=30, attempt_count=5)
    sure = update_mastery(base, ev(True, confidence=5))
    lucky = update_mastery(base, ev(True, confidence=1))
    assert sure.mastery_score > lucky.mastery_score


def test_fast_correct_beats_slow_correct():
    base = SkillState(mastery_score=30, attempt_count=5)
    fast = update_mastery(base, ev(True, time_ms=20_000, expected_time_ms=120_000))
    slow = update_mastery(base, ev(True, time_ms=600_000, expected_time_ms=120_000))
    assert fast.mastery_score > slow.mastery_score


def test_confidence_stored_separately_from_accuracy():
    s = update_mastery(SkillState(), ev(False, confidence=5))
    assert s.confidence == 1.0 and s.accuracy == 0.0  # divergence preserved for analytics


def test_deterministic():
    s = SkillState(mastery_score=42.5, attempt_count=3)
    e = ev(True, "hard", time_ms=90_000, confidence=3)
    assert update_mastery(s, e) == update_mastery(s, e)


def test_target_difficulty_bands():
    assert [target_difficulty(m) for m in (None, 10, 50, 90)] == ["easy", "easy", "medium", "hard"]


# ---------------- grading ----------------


def test_grade_objective_types():
    assert grade("mcq", {"correct": ["b"]}, {"selected": ["b"]}).correct
    assert not grade("multi_select", {"correct": ["a", "b"]}, {"selected": ["a"]}).correct
    assert grade("numerical", {"value": 6, "tolerance": 0.1}, {"value": 6.05}).correct
    assert not grade("numerical", {"value": 6, "tolerance": 0}, {"value": 6.05}).correct
    assert grade("output_prediction", {"expected_output": "[1, 2]"},
                 {"text": " [1, 2]  \n"}).correct


def test_grade_unanswered_is_wrong_not_pending():
    r = grade("mcq", {"correct": ["a"]}, None)
    assert r.gradable and not r.correct


def test_code_types_are_never_graded_in_backend():
    for t in ("coding", "sql"):
        r = grade(t, {}, {"code": "print(1)", "text": "select 1"})
        assert not r.gradable and r.judged_by == "pending"


def test_theory_keyword_heuristic():
    key = {"key_points": ["separate address space", "threads share heap memory",
                          "context switch cost"]}
    good = grade("theory", key, {"text": "Processes have a separate address space while threads "
                                         "share heap memory; context switch cost is higher."})
    bad = grade("theory", key, {"text": "They are basically the same."})
    assert good.correct and good.judged_by == "heuristic"
    assert not bad.correct


# ---------------- composition & streak ----------------


def test_quotas_sum_exactly():
    for n in range(0, 23):
        assert sum(quotas(n, {"easy": 0.3, "medium": 0.5, "hard": 0.2}).values()) == n


def test_balance_respects_mix_and_spreads_topics():
    pool = [Candidate(i, d, t) for i, (d, t) in enumerate(
        [(d, t) for d in ("easy", "medium", "hard") for t in (1, 2, 3) for _ in range(4)])]
    picked = balance(pool, 10, {"easy": 0.3, "medium": 0.5, "hard": 0.2}, random.Random(1))
    diffs = [c.difficulty for c in picked]
    assert (diffs.count("easy"), diffs.count("medium"), diffs.count("hard")) == (3, 5, 2)
    mediums = [c.topic_id for c in picked if c.difficulty == "medium"]
    assert len(set(mediums)) == 3  # round-robin across topics
    assert len({c.id for c in picked}) == 10


def test_balance_fills_shortfall_from_neighbour():
    pool = [Candidate(i, "medium", 1) for i in range(10)]
    picked = balance(pool, 5, {"easy": 0.4, "medium": 0.2, "hard": 0.4}, random.Random(0))
    assert len(picked) == 5 and len({c.id for c in picked}) == 5


def test_streak():
    d = date(2026, 9, 25)
    assert next_streak(None, d, 0) == 1
    assert next_streak(date(2026, 9, 24), d, 4) == 5
    assert next_streak(d, d, 5) == 5
    assert next_streak(date(2026, 9, 20), d, 9) == 1
