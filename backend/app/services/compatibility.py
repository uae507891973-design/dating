"""Функция совместимости (заготовка для подбора, Стадия 2).

Считает совместимость двух пользователей по ответам теста с учётом важности
вопросов (модель в духе OkCupid). Возвращает интегральный score 0..100 и вклад
каждой категории — это сырьё для объяснимого мэтчинга («Почему вы подходите»).
"""

from dataclasses import dataclass

from app.models.psychotest import IMPORTANCE_WEIGHT, Importance
from app.services.psychotest import QUESTIONS_BY_ID, Category

# Ответ: question_id -> (value, importance)
AnswerMap = dict[str, tuple[int, Importance]]


@dataclass
class CompatibilityResult:
    score: int                       # 0..100
    category_contributions: dict[str, float]  # категория -> совпадение 0..1
    common_questions: int


def _question_match(qid: str, a_value: int, b_value: int) -> float:
    """Совпадение по одному вопросу: 1.0 — идеально, 0.0 — максимально далеко."""
    q = QUESTIONS_BY_ID.get(qid)
    if q is None:
        return 0.0
    if q.ordered:
        span = q.max_value - q.min_value or 1
        return 1.0 - abs(a_value - b_value) / span
    return 1.0 if a_value == b_value else 0.0


def compute_compatibility(
    a: AnswerMap,
    b: AnswerMap,
    category_weights: dict[str, float] | None = None,
) -> CompatibilityResult:
    """Совместимость двух наборов ответов.

    `category_weights` (scrutability) — множители важности категорий с точки
    зрения первого пользователя (a). При None используется симметричный расчёт.
    """
    common = set(a) & set(b)
    if not common:
        return CompatibilityResult(
            score=0, category_contributions={}, common_questions=0
        )

    weights = category_weights or {}
    weighted_sum = 0.0
    weight_total = 0.0
    cat_match: dict[str, float] = {}
    cat_weight: dict[str, float] = {}

    for qid in common:
        a_val, a_imp = a[qid]
        b_val, b_imp = b[qid]
        q = QUESTIONS_BY_ID[qid]
        cat = q.category.value
        # Вес вопроса — максимум важности из двух пользователей,
        # домноженный на множитель важности категории (scrutability).
        weight = float(max(IMPORTANCE_WEIGHT[a_imp], IMPORTANCE_WEIGHT[b_imp]))
        weight *= weights.get(cat, 1.0)
        if weight <= 0:
            continue
        match = _question_match(qid, a_val, b_val)

        weighted_sum += match * weight
        weight_total += weight

        cat_match[cat] = cat_match.get(cat, 0.0) + match * weight
        cat_weight[cat] = cat_weight.get(cat, 0.0) + weight

    score = int(round(100 * weighted_sum / weight_total)) if weight_total else 0
    contributions = {
        cat: round(cat_match[cat] / cat_weight[cat], 4)
        for cat in cat_match
        if cat_weight[cat] > 0
    }
    return CompatibilityResult(
        score=score,
        category_contributions=contributions,
        common_questions=len(common),
    )


# Человекочитаемые названия категорий (для будущих объяснений, Стадия 2).
CATEGORY_LABELS: dict[str, str] = {
    Category.values.value: "общие ценности",
    Category.goals.value: "совпадение целей",
    Category.lifestyle.value: "образ жизни",
    Category.family.value: "взгляды на семью",
    Category.communication.value: "стиль общения",
}
