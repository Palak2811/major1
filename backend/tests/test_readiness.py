import pytest

from app.services.readiness import (
    DEFAULT_WEIGHTS,
    coding_component,
    consistency_component,
    dsa_component,
    rank_weaknesses,
    readiness,
)


def test_equation_3_1_hand_computed():
    c = {"dsa": 80, "csf": 60, "coding": 70, "aptitude": 90, "interview": 0, "consistency": 50}
    # 0.25·80 + 0.20·60 + 0.20·70 + 0.15·90 + 0.10·0 + 0.10·50
    # = 20 + 12 + 14 + 13.5 + 0 + 5 = 64.5
    assert readiness(c) == 64.5


def test_equation_3_1_second_case_with_decimals():
    c = {"dsa": 45.2, "csf": 33.3, "coding": 12.5, "aptitude": 100, "interview": 0,
         "consistency": 7.14}
    # 11.3 + 6.66 + 2.5 + 15 + 0 + 0.714 = 36.174 -> 36.17
    assert readiness(c) == 36.17


def test_company_weight_override():
    tcs = {"dsa": 0.15, "csf": 0.15, "coding": 0.15, "aptitude": 0.30, "interview": 0.15,
           "consistency": 0.10}
    c = {"dsa": 40, "csf": 40, "coding": 40, "aptitude": 100, "interview": 0, "consistency": 0}
    # 0.15·40·3 + 0.30·100 = 18 + 30 = 48 ; default weights give 0.65·40 + 0.15·100 = 41
    assert readiness(c, tcs) == 48.0
    assert readiness(c) == 41.0


def test_bounds_and_validation():
    top = dict.fromkeys(DEFAULT_WEIGHTS, 100.0)
    assert readiness(top) == 100.0
    assert readiness(dict.fromkeys(DEFAULT_WEIGHTS, 0.0)) == 0.0
    assert readiness({**top, "dsa": 150}) == 100.0  # components clamp to [0, 100]
    with pytest.raises(ValueError):
        readiness(top, {**DEFAULT_WEIGHTS, "dsa": 0.5})  # weights must sum to 1
    with pytest.raises(ValueError):
        readiness({"dsa": 1})


def test_component_formulas():
    assert dsa_component(None, None) == 0
    assert dsa_component(60, None) == 60
    assert dsa_component(60, 0.5) == pytest.approx(0.7 * 60 + 15)
    assert coding_component(0, 0, []) == 0
    assert coding_component(4, 2, [1.0, 0.5]) == pytest.approx(70 * 0.5 + 30 * 0.75)
    assert consistency_component(14, 14) == 100
    assert consistency_component(7, 7) == 50
    assert consistency_component(30, 3) == pytest.approx(50 + 50 * 3 / 14)


def test_weakness_ranking_prefers_company_emphasis():
    nodes = [("Graphs", "DSA", 30.0, 5), ("Normalization", "DBMS", 10.0, 4),
             ("Dynamic Programming", "DSA", None, 0), ("Percentages", "Aptitude", 20.0, 3)]
    ranked = rank_weaknesses(nodes, {"DSA": 50, "DBMS": 10, "Aptitude": 5},
                             frequent={"Dynamic Programming"})
    assert [w.name for w in ranked][:2] == ["Dynamic Programming", "Graphs"]
    assert ranked[0].reason.startswith("frequently tested")
