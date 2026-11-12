from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.base import utc_now
from app.db.session import get_db
from app.models.entities import (
    Alert, Appointment, AuditLog, CareProfile, ConsentRecord, Game, GameSession,
    DataPermission, GuardianLink, LocationEvent, LocationPermission, Medication, MediaAsset, Role,
    MedicationEvent, MemoryPerson, MemoryPlace, QuizAttempt, Reminder, ReminderEvent,
    User, UserRole, WellbeingCheckin,
)
from app.schemas.api import GameSessionFinish, GameSessionStart, LocationCreate, LocationPermissionUpdate
from app.services.authorization import require_dependent_access, require_role

router = APIRouter(tags=["orientation, reports and safety"])


@router.get("/dependents/{dependent_id}/orientation")
def orientation(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    require_dependent_access(db, current, dependent_id, "profile")
    profile = db.scalar(select(CareProfile).where(CareProfile.user_id == dependent_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Care profile not found")
    people = db.scalars(select(MemoryPerson).where(MemoryPerson.dependent_id == dependent_id).order_by(MemoryPerson.created_at.desc()).limit(8)).all()
    places = db.scalars(select(MemoryPlace).where(MemoryPlace.dependent_id == dependent_id).order_by(MemoryPlace.created_at.desc()).limit(8)).all()
    return {
        "preferred_name": profile.preferred_name, "mode": profile.mode, "timezone": profile.timezone,
        "people": [{"id": str(item.id), "name": item.name, "relationship_label": item.relationship_label, "media_id": str(item.media_id) if item.media_id else None} for item in people],
        "places": [{"id": str(item.id), "name": item.name, "description": item.description, "media_id": str(item.media_id) if item.media_id else None} for item in places],
    }


@router.get("/dependents/{dependent_id}/reports")
def reports(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    require_dependent_access(db, current, dependent_id, "reports")
    since = utc_now() - timedelta(days=30)
    medication_ids = select(Medication.id).where(Medication.dependent_id == dependent_id)
    medication_rows = db.execute(select(MedicationEvent.event_type, func.count(MedicationEvent.id)).where(
        MedicationEvent.medication_id.in_(medication_ids), MedicationEvent.occurred_at >= since
    ).group_by(MedicationEvent.event_type)).all()
    reminder_rows = db.execute(select(ReminderEvent.event_type, func.count(ReminderEvent.id)).join(
        Reminder, Reminder.id == ReminderEvent.reminder_id
    ).where(Reminder.dependent_id == dependent_id, ReminderEvent.occurred_at >= since).group_by(ReminderEvent.event_type)).all()
    quiz_count = db.scalar(select(func.count(QuizAttempt.id)).where(QuizAttempt.dependent_id == dependent_id, QuizAttempt.answered_at >= since)) or 0
    game_count = db.scalar(select(func.count(GameSession.id)).where(GameSession.dependent_id == dependent_id, GameSession.started_at >= since)) or 0
    appointments = db.scalars(select(Appointment).where(Appointment.dependent_id == dependent_id, Appointment.starts_at >= utc_now()).order_by(Appointment.starts_at).limit(5)).all()
    alerts = db.scalars(select(Alert).where(Alert.dependent_id == dependent_id).order_by(Alert.created_at.desc()).limit(10)).all()
    wellbeing_allowed = current.id == dependent_id
    if not wellbeing_allowed:
        link = db.scalar(select(GuardianLink).where(GuardianLink.guardian_id == current.id, GuardianLink.dependent_id == dependent_id, GuardianLink.status == "active"))
        wellbeing_allowed = bool(link and db.scalar(select(DataPermission.id).where(DataPermission.link_id == link.id, DataPermission.category == "wellbeing", DataPermission.allowed.is_(True))))
    checkins = db.scalars(select(WellbeingCheckin).where(WellbeingCheckin.dependent_id == dependent_id, WellbeingCheckin.submitted_at >= since).order_by(WellbeingCheckin.submitted_at.desc()).limit(20)).all() if wellbeing_allowed else []
    return {
        "period_days": 30,
        "medication_events": {str(name): count for name, count in medication_rows},
        "activity_events": {str(name): count for name, count in reminder_rows},
        "quiz_attempts": quiz_count, "game_sessions": game_count,
        "appointments": [{"id": str(x.id), "title": x.title, "starts_at": x.starts_at.isoformat(), "location_label": x.location_label} for x in appointments],
        "alerts": [{"id": str(x.id), "alert_type": x.alert_type, "severity": x.severity, "status": x.status, "message": x.message, "created_at": x.created_at.isoformat()} for x in alerts],
        "wellbeing": [{"id": str(x.id), "submitted_at": x.submitted_at.isoformat(), "declined": x.declined, "response": x.response} for x in checkins],
    }


@router.post("/dependents/{dependent_id}/alerts/help", status_code=201)
def request_help(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    if current.id != dependent_id:
        raise HTTPException(status_code=403, detail="Only the dependent can send a help request")
    require_dependent_access(db, current, dependent_id, "emergency")
    alert = Alert(dependent_id=dependent_id, alert_type="help_request", severity="high", message="The person receiving care asked for help.")
    db.add(alert)
    db.add(AuditLog(actor_id=current.id, action="alert.help_request", resource_type="alert", dependent_id=dependent_id))
    db.commit()
    db.refresh(alert)
    return {"id": str(alert.id), "status": alert.status}


def _location_permission(db: Session, dependent_id: UUID) -> LocationPermission | None:
    return db.scalar(select(LocationPermission).where(LocationPermission.dependent_id == dependent_id))


@router.get("/dependents/{dependent_id}/location/permission")
def get_location_permission(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    if current.id == dependent_id:
        require_role(db, current, "DEPENDENT")
    else:
        require_dependent_access(db, current, dependent_id, "location")
    item = _location_permission(db, dependent_id)
    return {"dependent_id": str(dependent_id), "enabled": bool(item and item.enabled), "purpose": item.purpose if item else "", "retention_days": item.retention_days if item else 7}


@router.put("/dependents/{dependent_id}/location/permission")
def update_location_permission(dependent_id: UUID, payload: LocationPermissionUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    if current.id != dependent_id:
        raise HTTPException(status_code=403, detail="Only the dependent can control location sharing")
    require_role(db, current, "DEPENDENT")
    item = _location_permission(db, dependent_id)
    if not item:
        item = LocationPermission(dependent_id=dependent_id)
        db.add(item)
    item.enabled = payload.enabled
    item.purpose = payload.purpose.strip()
    item.retention_days = payload.retention_days
    db.add(ConsentRecord(subject_id=dependent_id, actor_id=current.id, purpose="location_sharing", policy_version="1", granted=payload.enabled))
    db.add(AuditLog(actor_id=current.id, action="location.permission.update", resource_type="location_permission", dependent_id=dependent_id))
    links = db.scalars(select(GuardianLink).where(GuardianLink.dependent_id == dependent_id, GuardianLink.status == "active")).all()
    for link in links:
        grant = db.scalar(select(DataPermission).where(DataPermission.link_id == link.id, DataPermission.category == "location"))
        if grant is None:
            db.add(DataPermission(link_id=link.id, category="location", allowed=payload.enabled, granted_by=current.id))
        else:
            grant.allowed = payload.enabled
            grant.granted_by = current.id
    if not payload.enabled:
        db.query(LocationEvent).filter(LocationEvent.dependent_id == dependent_id).delete(synchronize_session=False)
    db.commit()
    return {"dependent_id": str(dependent_id), "enabled": item.enabled, "purpose": item.purpose, "retention_days": item.retention_days}


@router.post("/dependents/{dependent_id}/location/events", status_code=201)
def create_location_event(dependent_id: UUID, payload: LocationCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    if current.id != dependent_id:
        raise HTTPException(status_code=403, detail="Location can only be shared by the dependent")
    require_role(db, current, "DEPENDENT")
    permission = _location_permission(db, dependent_id)
    if not permission or not permission.enabled:
        raise HTTPException(status_code=403, detail="Location sharing is not enabled")
    event = LocationEvent(dependent_id=dependent_id, latitude=payload.latitude, longitude=payload.longitude)
    db.add(event)
    db.add(AuditLog(actor_id=current.id, action="location.event.create", resource_type="location_event", dependent_id=dependent_id))
    db.query(LocationEvent).filter(LocationEvent.dependent_id == dependent_id, LocationEvent.recorded_at < utc_now() - timedelta(days=permission.retention_days)).delete(synchronize_session=False)
    db.commit()
    db.refresh(event)
    return {"id": str(event.id), "recorded_at": event.recorded_at.isoformat()}


@router.get("/dependents/{dependent_id}/location")
def last_location(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    if current.id == dependent_id:
        require_role(db, current, "DEPENDENT")
    else:
        require_dependent_access(db, current, dependent_id, "location")
    permission = _location_permission(db, dependent_id)
    if not permission or not permission.enabled:
        return {"enabled": False, "location": None}
    event = db.scalar(select(LocationEvent).where(LocationEvent.dependent_id == dependent_id).order_by(LocationEvent.recorded_at.desc()).limit(1))
    if not event:
        return {"enabled": True, "location": None}
    return {"enabled": True, "location": {"latitude": event.latitude, "longitude": event.longitude, "recorded_at": event.recorded_at.isoformat()}}


@router.post("/games/{game_id}/sessions", status_code=201)
def start_game_session(game_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    game = db.get(Game, game_id)
    if not game or not game.active:
        raise HTTPException(status_code=404, detail="Game not found")
    if current.id != game.dependent_id:
        raise HTTPException(status_code=403, detail="Only the dependent can start a game")
    session = GameSession(game_id=game.id, dependent_id=current.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": str(session.id), "started_at": session.started_at.isoformat()}


@router.post("/dependents/{dependent_id}/game-sessions", status_code=201)
def start_casual_game(
    dependent_id: UUID,
    payload: GameSessionStart,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if current.id != dependent_id:
        raise HTTPException(status_code=403, detail="Only the dependent can start a game")
    require_role(db, current, "DEPENDENT")
    titles = {
        "sequence_memory": "Sequence Memory",
        "tile_memory": "Tile Memory",
        "pattern_memory": "Pattern Memory",
        "matching_pairs": "Matching Pairs",
        "odd_one_out": "Odd One Out",
    }
    game = db.scalar(select(Game).where(
        Game.dependent_id == dependent_id,
        Game.game_type == payload.game_type,
    ).order_by(Game.created_at).limit(1))
    if game is not None and not game.active:
        raise HTTPException(status_code=403, detail="This game is paused by your guardian")
    if game is None:
        game = Game(
            dependent_id=dependent_id,
            title=titles[payload.game_type],
            game_type=payload.game_type,
            configuration={"difficulty": "gentle", "kind": "general"},
        )
        db.add(game)
        db.flush()
    session = GameSession(game_id=game.id, dependent_id=dependent_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": str(session.id), "game_type": payload.game_type, "title": titles[payload.game_type]}


@router.post("/game-sessions/{session_id}/finish")
def finish_game_session(session_id: UUID, payload: GameSessionFinish, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    session = db.get(GameSession, session_id)
    if not session or session.dependent_id != current.id:
        raise HTTPException(status_code=404, detail="Game session not found")
    if session.finished_at:
        raise HTTPException(status_code=409, detail="This game session is already complete")
    session.finished_at = utc_now()
    session.interactions = payload.interactions
    session.result = payload.result
    db.commit()
    return {"id": str(session.id), "status": "completed"}


@router.get("/admin/overview")
def admin_overview(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    require_role(db, current, "ADMIN")
    def count(model: type) -> int:
        return db.scalar(select(func.count()).select_from(model)) or 0
    role_counts = db.execute(select(Role.name, func.count(UserRole.user_id))
                             .join(UserRole, UserRole.role_id == Role.id).group_by(Role.name)).all()
    return {"users": count(User), "guardians": {str(k): v for k, v in role_counts}, "active_links": db.scalar(select(func.count(GuardianLink.id)).where(GuardianLink.status == "active")) or 0,
            "media_assets": count(MediaAsset), "open_alerts": db.scalar(select(func.count(Alert.id)).where(Alert.status == "open")) or 0}
