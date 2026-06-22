"""Каталог вопросов теста совместимости и расчёт психопрофиля.

Каталог — источник правды (статическая конфигурация). Ответы пользователей
хранятся в БД и ссылаются на стабильные `id` вопросов. На основе ответов
строится психопрофиль (вектор по категориям), используемый в подборе.
"""

from dataclasses import dataclass
from enum import Enum


class Category(str, Enum):
    values = "values"          # ценности
    goals = "goals"            # цели/намерения
    lifestyle = "lifestyle"    # образ жизни
    family = "family"          # отношение к семье
    communication = "communication"  # коммуникация


@dataclass(frozen=True)
class Option:
    value: int
    label: str


@dataclass(frozen=True)
class Question:
    id: str
    category: Category
    text: str
    options: tuple[Option, ...]
    ordered: bool = True  # упорядоченная шкала (иначе — категориальный выбор)

    @property
    def max_value(self) -> int:
        return max(o.value for o in self.options)

    @property
    def min_value(self) -> int:
        return min(o.value for o in self.options)


def _scale(text: str, category: Category, qid: str) -> Question:
    """Вопрос-шкала 1..5 (полностью не согласен → полностью согласен)."""
    return Question(
        id=qid,
        category=category,
        text=text,
        options=(
            Option(1, "Совсем не про меня"),
            Option(2, "Скорее нет"),
            Option(3, "Нейтрально"),
            Option(4, "Скорее да"),
            Option(5, "Точно про меня"),
        ),
        ordered=True,
    )


# Каталог: (id, категория, текст). Все вопросы — шкала 1..5.
_CATALOG: tuple[tuple[str, Category, str], ...] = (
    ("val_shared", Category.values, "Для меня важны общие ценности с партнёром"),
    ("val_honesty", Category.values, "Честность важнее комфорта в отношениях"),
    ("val_space", Category.values, "Я ценю личное пространство партнёра"),
    ("goal_serious", Category.goals, "Я ищу серьёзные долгосрочные отношения"),
    ("goal_marriage", Category.goals, "Для меня важно прийти к браку"),
    ("goal_cohab", Category.goals, "Я готов(а) к совместному быту в будущем"),
    ("life_active", Category.lifestyle, "Я веду активный и здоровый образ жизни"),
    ("life_travel", Category.lifestyle, "Мне важны путешествия и впечатления"),
    ("life_home", Category.lifestyle, "Я предпочитаю спокойный домашний отдых"),
    ("fam_children", Category.family, "Я хочу детей"),
    ("fam_priority", Category.family, "Семья — главный приоритет в жизни"),
    ("fam_traditional", Category.family, "Мне близки традиционные ценности"),
    ("com_open", Category.communication, "Я открыто говорю о своих чувствах"),
    ("com_conflict", Category.communication, "Конфликты лучше решать сразу"),
    ("com_frequency", Category.communication, "Мне важно частое общение"),
    ("com_compromise", Category.communication, "Я готов(а) на компромиссы"),
)

QUESTIONS: tuple[Question, ...] = tuple(
    _scale(text, category, qid) for qid, category, text in _CATALOG
)

# Быстрый доступ по id.
QUESTIONS_BY_ID: dict[str, Question] = {q.id: q for q in QUESTIONS}


def compute_psychoprofile(
    answers: dict[str, int],
) -> dict[str, float]:
    """Построить вектор психопрофиля: категория -> нормализованное среднее 0..1."""
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for qid, value in answers.items():
        q = QUESTIONS_BY_ID.get(qid)
        if q is None:
            continue
        span = q.max_value - q.min_value or 1
        normalized = (value - q.min_value) / span
        cat = q.category.value
        sums[cat] = sums.get(cat, 0.0) + normalized
        counts[cat] = counts.get(cat, 0) + 1
    return {cat: round(sums[cat] / counts[cat], 4) for cat in sums}
