"""Юнит-тесты функции совместимости."""

from app.models.psychotest import Importance
from app.services.compatibility import compute_compatibility
from app.services.psychotest import QUESTIONS, compute_psychoprofile


def _answers(value: int, importance=Importance.high) -> dict:
    return {q.id: (value, importance) for q in QUESTIONS}


def test_identical_answers_score_100() -> None:
    a = _answers(5)
    b = _answers(5)
    result = compute_compatibility(a, b)
    assert result.score == 100
    assert result.common_questions == len(QUESTIONS)
    assert all(v == 1.0 for v in result.category_contributions.values())


def test_opposite_answers_score_0() -> None:
    a = _answers(1)
    b = _answers(5)
    result = compute_compatibility(a, b)
    assert result.score == 0


def test_symmetry() -> None:
    a = {q.id: (i % 5 + 1, Importance.medium) for i, q in enumerate(QUESTIONS)}
    b = {q.id: ((i + 2) % 5 + 1, Importance.low) for i, q in enumerate(QUESTIONS)}
    assert compute_compatibility(a, b).score == compute_compatibility(b, a).score


def test_no_common_questions() -> None:
    result = compute_compatibility({}, {})
    assert result.score == 0
    assert result.common_questions == 0


def test_psychoprofile_normalized() -> None:
    vector = compute_psychoprofile({q.id: 5 for q in QUESTIONS})
    assert vector
    assert all(0.0 <= v <= 1.0 for v in vector.values())
