"""Жалобы и блокировки пользователей."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Block, Report, User
from app.schemas.safety import BlockIn, ReportIn, ReportOut
from app.services.analytics import track_event
from app.services.audit import write_audit

router = APIRouter(tags=["safety"])


@router.post("/reports", response_model=ReportOut, status_code=201)
async def create_report(
    data: ReportIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportOut:
    if data.target_user_id == user.id:
        raise HTTPException(status_code=400, detail="cannot report yourself")

    report = Report(
        reporter_id=user.id, target_id=data.target_user_id, reason=data.reason
    )
    db.add(report)
    write_audit(db, user.id, "report_created", str(data.target_user_id))
    await db.commit()
    await db.refresh(report)

    track_event("report_created", {"reporter": str(user.id)})
    return ReportOut(id=report.id, status=report.status.value)


@router.post("/blocks", status_code=204)
async def create_block(
    data: BlockIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if data.target_user_id == user.id:
        raise HTTPException(status_code=400, detail="cannot block yourself")

    exists = await db.get(Block, (user.id, data.target_user_id))
    if exists is None:
        db.add(Block(blocker_id=user.id, blocked_id=data.target_user_id))
        write_audit(db, user.id, "block_created", str(data.target_user_id))
        await db.commit()
        track_event("user_blocked", {"blocker": str(user.id)})


@router.get("/blocks", response_model=list[uuid.UUID])
async def list_blocks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[uuid.UUID]:
    rows = (
        await db.execute(
            select(Block.blocked_id).where(Block.blocker_id == user.id)
        )
    ).scalars().all()
    return list(rows)


@router.delete("/blocks/{target_user_id}", status_code=204)
async def delete_block(
    target_user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    block = await db.get(Block, (user.id, target_user_id))
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    await db.delete(block)
    await db.commit()
