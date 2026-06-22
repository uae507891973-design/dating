"""Онбординг: тест совместимости и выбор намерения."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Profile, Psychoprofile, PsychotestAnswer, User
from app.models.user import UserStatus
from app.schemas.onboarding import (
    OnboardingStatusOut,
    OptionOut,
    QuestionOut,
    TestSubmitIn,
)
from app.services.analytics import track_event
from app.services.psychotest import (
    QUESTIONS,
    QUESTIONS_BY_ID,
    compute_psychoprofile,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/questions", response_model=list[QuestionOut])
async def get_questions() -> list[QuestionOut]:
    """Вернуть каталог вопросов теста совместимости."""
    return [
        QuestionOut(
            id=q.id,
            category=q.category.value,
            text=q.text,
            ordered=q.ordered,
            options=[OptionOut(value=o.value, label=o.label) for o in q.options],
        )
        for q in QUESTIONS
    ]


@router.post("/answers", response_model=OnboardingStatusOut)
async def submit_answers(
    data: TestSubmitIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusOut:
    """Сохранить ответы, рассчитать психопрофиль и зафиксировать намерение."""
    # Валидация: все вопросы из каталога, значения в допустимом диапазоне.
    for ans in data.answers:
        q = QUESTIONS_BY_ID.get(ans.question_id)
        if q is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unknown question: {ans.question_id}",
            )
        if not (q.min_value <= ans.value <= q.max_value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"value out of range for {ans.question_id}",
            )

    # Перезаписываем ответы пользователя (идемпотентность повторного прохождения).
    await db.execute(
        delete(PsychotestAnswer).where(PsychotestAnswer.user_id == user.id)
    )
    for ans in data.answers:
        db.add(
            PsychotestAnswer(
                user_id=user.id,
                question_id=ans.question_id,
                value=ans.value,
                importance=ans.importance,
            )
        )

    # Психопрофиль (вектор по категориям).
    vector = compute_psychoprofile({a.question_id: a.value for a in data.answers})
    profile_vec = await db.get(Psychoprofile, user.id)
    if profile_vec is None:
        db.add(Psychoprofile(user_id=user.id, vector=vector))
    else:
        profile_vec.vector = vector

    # Намерение фиксируем в анкете (создаём при отсутствии).
    profile = await db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id, intent=data.intent)
        db.add(profile)
    else:
        profile.intent = data.intent

    # Тест пройден — активируем пользователя.
    if user.status == UserStatus.pending:
        user.status = UserStatus.active

    await db.commit()
    track_event(
        "test_completed",
        {
            "user_id": str(user.id),
            "answered": len(data.answers),
            "intent": data.intent.value,
        },
    )

    return OnboardingStatusOut(
        test_completed=True,
        answered_count=len(data.answers),
        total_questions=len(QUESTIONS),
        intent=data.intent,
        psychoprofile=vector,
    )


@router.get("/status", response_model=OnboardingStatusOut)
async def onboarding_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusOut:
    """Текущее состояние онбординга пользователя."""
    answers = (
        await db.execute(
            select(PsychotestAnswer).where(PsychotestAnswer.user_id == user.id)
        )
    ).scalars().all()
    profile = await db.get(Profile, user.id)
    profile_vec = await db.get(Psychoprofile, user.id)

    return OnboardingStatusOut(
        test_completed=len(answers) > 0,
        answered_count=len(answers),
        total_questions=len(QUESTIONS),
        intent=profile.intent if profile else None,
        psychoprofile=profile_vec.vector if profile_vec else {},
    )
