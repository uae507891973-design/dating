"""Тест «Кто вы в паре?»: вопросы, результат, добавление в профиль."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Profile, User
from app.schemas.personality import (
    ArchetypeOut,
    POptionOut,
    PQuestionOut,
    PSubmitIn,
    PTestMetaOut,
)
from app.services.analytics import track_event
from app.services.personality import (
    ARCHETYPES,
    DISCLAIMER,
    PERSONALITY_QUESTIONS,
    TEST_TITLE,
    compute_archetype,
)

router = APIRouter(prefix="/personality", tags=["personality"])


def _archetype_out(
    key: str, scores: dict[str, int] | None = None, in_profile: bool = False
) -> ArchetypeOut:
    a = ARCHETYPES[key]
    return ArchetypeOut(
        key=a.key,
        title=a.title,
        emoji=a.emoji,
        short=a.short,
        description=a.description,
        strengths=list(a.strengths),
        in_pair=a.in_pair,
        disclaimer=DISCLAIMER,
        scores=scores or {},
        in_profile=in_profile,
    )


@router.get("/questions", response_model=PTestMetaOut)
async def get_questions() -> PTestMetaOut:
    """Вопросы теста (лёгкий тест после вступительного)."""
    return PTestMetaOut(
        title=TEST_TITLE,
        disclaimer=DISCLAIMER,
        questions=[
            PQuestionOut(
                id=q.id,
                text=q.text,
                options=[POptionOut(id=o.id, label=o.label) for o in q.options],
            )
            for q in PERSONALITY_QUESTIONS
        ],
    )


@router.post("/submit", response_model=ArchetypeOut)
async def submit(
    data: PSubmitIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArchetypeOut:
    """Рассчитать типаж; по желанию — добавить в профиль."""
    answers = {a.question_id: a.option_id for a in data.answers}
    try:
        key, scores = compute_archetype(answers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    in_profile = False
    if data.add_to_profile:
        profile = await db.get(Profile, user.id)
        if profile is None:
            profile = Profile(user_id=user.id)
            db.add(profile)
        profile.personality_archetype = key
        await db.commit()
        in_profile = True

    track_event(
        "personality_completed",
        {"user_id": str(user.id), "archetype": key, "saved": in_profile},
    )
    return _archetype_out(key, scores, in_profile)


@router.get("/result", response_model=ArchetypeOut)
async def my_result(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArchetypeOut:
    """Типаж, сохранённый в профиле."""
    profile = await db.get(Profile, user.id)
    if profile is None or profile.personality_archetype is None:
        raise HTTPException(status_code=404, detail="no personality result")
    return _archetype_out(profile.personality_archetype, in_profile=True)


@router.delete("/result", status_code=204)
async def remove_from_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Убрать типаж из профиля."""
    profile = await db.get(Profile, user.id)
    if profile is not None and profile.personality_archetype is not None:
        profile.personality_archetype = None
        await db.commit()
