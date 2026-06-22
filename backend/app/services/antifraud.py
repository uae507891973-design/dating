"""Антифрод-движок: поведенческие сигналы, risk-score, авто-флаги.

На фундаменте — правила на основе агрегатов поведения. Реальная ML-модель и
графовый анализ сетей мошенников подключаются позже через ту же точку входа.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Like, Message, Report, RiskFlag, User
from app.models.antifraud import FlagStatus
from app.models.safety import ReportStatus
from app.services.analytics import track_event
from app.services.audit import write_audit

settings = get_settings()


@dataclass
class RiskAssessment:
    risk_score: int
    reasons: list[str] = field(default_factory=list)


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


async def evaluate_user(db: AsyncSession, user: User) -> RiskAssessment:
    """Посчитать risk-score 0..100 по поведенческим сигналам."""
    cutoff = (
        datetime.now(UTC) - timedelta(seconds=settings.antifraud_window_sec)
    ).replace(tzinfo=None)

    # Последние сообщения пользователя.
    messages = (
        await db.execute(
            select(Message)
            .where(Message.sender_id == user.id)
            .order_by(desc(Message.created_at))
            .limit(200)
        )
    ).scalars().all()
    recent_msgs = [m for m in messages if _to_naive_utc(m.created_at) >= cutoff]

    # Лайки пользователя.
    likes = (
        await db.execute(
            select(Like)
            .where(Like.from_user == user.id)
            .order_by(desc(Like.created_at))
            .limit(500)
        )
    ).scalars().all()
    recent_likes = [
        likes_row
        for likes_row in likes
        if _to_naive_utc(likes_row.created_at) >= cutoff
    ]

    # Открытые жалобы на пользователя.
    reports_count = len(
        (
            await db.execute(
                select(Report.id).where(
                    Report.target_id == user.id,
                    Report.status == ReportStatus.open,
                )
            )
        ).all()
    )

    # Повторяющиеся (шаблонные) сообщения.
    duplicates = 0
    if recent_msgs:
        duplicates = Counter(m.body.strip().lower() for m in recent_msgs).most_common(
            1
        )[0][1]

    risk = 0
    reasons: list[str] = []

    if len(recent_msgs) > settings.antifraud_msg_velocity:
        risk += 30
        reasons.append("высокая частота сообщений")
    if duplicates >= settings.antifraud_duplicate_threshold:
        risk += 40
        reasons.append("повторяющиеся (шаблонные) сообщения")
    if len(recent_likes) > settings.antifraud_like_velocity:
        risk += 20
        reasons.append("аномальная частота лайков")
    if reports_count >= settings.antifraud_reports_threshold:
        risk += 40
        reasons.append("жалобы других пользователей")

    # Митигация: верифицированный аккаунт менее рискован.
    if user.is_verified:
        risk = int(risk * 0.5)

    return RiskAssessment(risk_score=min(risk, 100), reasons=reasons)


async def evaluate_and_apply(db: AsyncSession, user: User) -> RiskAssessment:
    """Оценить пользователя, обновить trust-score и при необходимости создать флаг."""
    assessment = await evaluate_user(db, user)
    user.trust_score = max(0, 100 - assessment.risk_score)

    if assessment.risk_score >= settings.antifraud_flag_threshold:
        existing = (
            await db.execute(
                select(RiskFlag).where(
                    RiskFlag.user_id == user.id,
                    RiskFlag.status == FlagStatus.open,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                RiskFlag(
                    user_id=user.id,
                    risk_score=assessment.risk_score,
                    reasons=assessment.reasons,
                )
            )
            write_audit(db, None, "antifraud_flag", str(user.id))
            track_event(
                "antifraud_flag",
                {"user_id": str(user.id), "risk": assessment.risk_score},
            )
        else:
            existing.risk_score = assessment.risk_score
            existing.reasons = assessment.reasons

    await db.commit()
    return assessment
