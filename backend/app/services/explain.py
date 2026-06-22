"""Объяснимый мэтчинг: честные причины «Почему вы подходите».

Причины формируются ТОЛЬКО из реальных факторов скоринга (вклад категорий
и совпадение намерений), чтобы не подрывать доверие ложными объяснениями.
"""

from app.models.profile import Intent
from app.services.compatibility import CATEGORY_LABELS, CompatibilityResult

# Порог, выше которого категория считается сильной стороной совпадения.
STRONG_THRESHOLD = 0.7
MAX_REASONS = 3

INTENT_LABELS: dict[Intent, str] = {
    Intent.marriage: "оба настроены на создание семьи",
    Intent.relationship: "обе цели — серьёзные отношения",
    Intent.friendship: "оба ищут общение и дружбу",
}


def generate_reasons(
    compat: CompatibilityResult,
    my_intent: Intent | None = None,
    their_intent: Intent | None = None,
) -> list[str]:
    """Топ причин совпадения (до MAX_REASONS), от сильнейшей к слабее."""
    reasons: list[str] = []

    # Совпадение намерений — сильный и честный сигнал.
    if my_intent is not None and my_intent == their_intent:
        reasons.append(INTENT_LABELS[my_intent])

    # Сильные категории по вкладу в совместимость.
    strong = sorted(
        (
            (cat, value)
            for cat, value in compat.category_contributions.items()
            if value >= STRONG_THRESHOLD
        ),
        key=lambda x: x[1],
        reverse=True,
    )
    for cat, _ in strong:
        label = CATEGORY_LABELS.get(cat)
        if label:
            reasons.append(label.capitalize())
        if len(reasons) >= MAX_REASONS:
            break

    return reasons[:MAX_REASONS]
