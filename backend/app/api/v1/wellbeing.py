from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.base import utc_now
from app.db.session import get_db
from app.models.entities import AuditLog, CareProfile, User, WellbeingCheckin
from app.schemas.api import WellbeingCheckinCreate
from app.services.authorization import has_role, require_dependent_access
from app.services.wellbeing import DIMENSIONS, public_questions, score_answers

router = APIRouter(tags=["daily wellbeing"])


def _timezone_for(db: Session, dependent_id: UUID) -> ZoneInfo:
    profile = db.scalar(select(CareProfile).where(CareProfile.user_id == dependent_id))
    try:
        return ZoneInfo(profile.timezone if profile else "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _local_date(db: Session, dependent_id: UUID) -> date:
    return utc_now().astimezone(_timezone_for(db, dependent_id)).date()


def _result(item: WellbeingCheckin | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "submitted_at": item.submitted_at.isoformat(),
        "overall_score": item.overall_score,
        "overall_category": item.overall_category,
        "category_scores": item.category_scores or {},
        "summary": item.summary,
        "answers": (item.response or {}).get("answers", []),
    }


@router.get("/dependents/{dependent_id}/wellbeing/questions")
def questions(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    require_dependent_access(db, current, dependent_id, "wellbeing")
    return public_questions()


@router.get("/dependents/{dependent_id}/wellbeing/today")
def today_status(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    require_dependent_access(db, current, dependent_id, "wellbeing")
    local_zone = _timezone_for(db, dependent_id)
    today = utc_now().astimezone(local_zone).date()
    item = db.scalar(select(WellbeingCheckin).where(
        WellbeingCheckin.dependent_id == dependent_id,
        WellbeingCheckin.checkin_date == today,
        WellbeingCheckin.reset_at.is_(None),
    ))
    next_date = today + timedelta(days=1)
    next_available = datetime.combine(next_date, time.min, tzinfo=local_zone)
    return {
        "date": today.isoformat(),
        "completed": item is not None,
        "next_available_date": next_date.isoformat(),
        "next_available_at": next_available.isoformat(),
        "result": _result(item),
    }


@router.post("/dependents/{dependent_id}/wellbeing-checkins", status_code=201)
def submit_checkin(
    dependent_id: UUID,
    payload: WellbeingCheckinCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if current.id != dependent_id or not has_role(db, current, "DEPENDENT"):
        raise HTTPException(status_code=403, detail="Only the dependent can submit their daily check-in")
    try:
        graded = score_answers(payload.answers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    checkin_date = _local_date(db, dependent_id)
    existing = db.scalar(select(WellbeingCheckin.id).where(
        WellbeingCheckin.dependent_id == dependent_id,
        WellbeingCheckin.checkin_date == checkin_date,
        WellbeingCheckin.reset_at.is_(None),
    ))
    if existing:
        raise HTTPException(status_code=409, detail="Today's check-in is already complete")

    item = WellbeingCheckin(
        dependent_id=dependent_id,
        checkin_date=checkin_date,
        submitted_at=utc_now(),
        response={"answers": graded["answers"]},
        overall_score=graded["overall_score"],
        overall_category=graded["overall_category"],
        category_scores=graded["category_scores"],
        summary=graded["summary"],
        declined=False,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Today's check-in is already complete") from exc
    db.refresh(item)
    local_zone = _timezone_for(db, dependent_id)
    next_date = checkin_date + timedelta(days=1)
    return {
        "date": checkin_date.isoformat(),
        "completed": True,
        "next_available_date": next_date.isoformat(),
        "next_available_at": datetime.combine(next_date, time.min, tzinfo=local_zone).isoformat(),
        "result": _result(item),
    }


@router.get("/dependents/{dependent_id}/wellbeing-checkins")
def checkin_history(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    require_dependent_access(db, current, dependent_id, "wellbeing")
    items = db.scalars(select(WellbeingCheckin).where(
        WellbeingCheckin.dependent_id == dependent_id,
    ).order_by(WellbeingCheckin.submitted_at.desc()).limit(100)).all()
    return [{
        "date": item.checkin_date.isoformat() if item.checkin_date else None,
        "submitted_at": item.submitted_at.isoformat(),
        "declined": item.declined,
        "overall_category": item.overall_category,
        "summary": item.summary,
        "response": item.response,
    } for item in items]


@router.get("/dependents/{dependent_id}/wellbeing/report")
def wellbeing_report(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    require_dependent_access(db, current, dependent_id, "wellbeing")
    local_zone = _timezone_for(db, dependent_id)
    today = utc_now().astimezone(local_zone).date()
    today_item = db.scalar(select(WellbeingCheckin).where(
        WellbeingCheckin.dependent_id == dependent_id,
        WellbeingCheckin.checkin_date == today,
        WellbeingCheckin.reset_at.is_(None),
    ))
    total = db.scalar(select(func.count(WellbeingCheckin.id)).where(
        WellbeingCheckin.dependent_id == dependent_id,
        WellbeingCheckin.checkin_date.is_not(None),
    )) or 0
    entries = db.scalars(select(WellbeingCheckin).where(
        WellbeingCheckin.dependent_id == dependent_id,
        WellbeingCheckin.checkin_date.is_not(None),
        WellbeingCheckin.overall_score.is_not(None),
    ).order_by(WellbeingCheckin.checkin_date.desc(), WellbeingCheckin.submitted_at.desc()).limit(14)).all()
    history = [{
        "date": item.checkin_date.isoformat(),
        "overall_score": item.overall_score,
        "overall_category": item.overall_category,
        "category_scores": item.category_scores or {},
        "submitted_at": item.submitted_at.isoformat(),
    } for item in reversed(entries)]
    trend: dict[str, dict[str, int | str | None]] = {}
    older, newer = entries[7:], entries[:7]
    for key, label in DIMENSIONS.items():
        old_values = [int((row.category_scores or {}).get(key, 0)) for row in older]
        new_values = [int((row.category_scores or {}).get(key, 0)) for row in newer]
        old_mean = round(sum(old_values) / len(old_values)) if old_values else None
        new_mean = round(sum(new_values) / len(new_values)) if new_values else None
        change = (new_mean - old_mean) if old_mean is not None and new_mean is not None else None
        trend[key] = {"label": label, "previous_average": old_mean, "recent_average": new_mean, "change": change}
    return {
        "today": today.isoformat(),
        "today_result": _result(today_item),
        "completed_checkins": total,
        "history": history,
        "category_trends": trend,
    }


@router.post("/dependents/{dependent_id}/wellbeing/today/reset")
def reset_today(
    dependent_id: UUID,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if has_role(db, current, "ADMIN"):
        pass  # Admins can reset completion without being granted access to private results.
    elif current.id != dependent_id:
        require_dependent_access(db, current, dependent_id, "wellbeing")
    else:
        raise HTTPException(status_code=403, detail="Only an authorized guardian or admin can reset completion")

    today = _local_date(db, dependent_id)
    item = db.scalar(select(WellbeingCheckin).where(
        WellbeingCheckin.dependent_id == dependent_id,
        WellbeingCheckin.checkin_date == today,
        WellbeingCheckin.reset_at.is_(None),
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="There is no completed check-in to reset today")
    item.reset_at = utc_now()  # Keep the original date and result in history; release today's unique slot.
    db.add(AuditLog(actor_id=current.id, action="wellbeing.today.reset", resource_type="wellbeing_checkin", dependent_id=dependent_id))
    db.commit()
    return {"status": "reset"}
