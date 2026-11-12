from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.base import utc_now
from app.db.session import get_db
from app.models.entities import Alert, Appointment, AuditLog, CareProfile, EmergencyContact, Game, Medication, MedicationEvent, Reminder, ReminderEvent, User
from app.schemas.api import AlertOut, AppointmentCreate, AppointmentOut, AppointmentUpdate, EmergencyContactCreate, EmergencyContactOut, EmergencyContactUpdate, GameCreate, GameOut, GameUpdate, MedicationCreate, MedicationOut, MedicationUpdate, ProfileOut, ProfileUpdate, ReminderCreate, ReminderOut, ReminderUpdate
from app.services.authorization import require_dependent_access, require_role

router = APIRouter(tags=["care data"])

GAME_TITLES = {
    "sequence_memory": "Sequence Memory",
    "tile_memory": "Tile Memory",
    "pattern_memory": "Pattern Memory",
    "matching_pairs": "Matching Pairs",
    "odd_one_out": "Odd One Out",
}


def _safe_game_configuration(configuration: dict[str, object] | None) -> dict[str, str]:
    difficulty = (configuration or {}).get("difficulty")
    if difficulty not in {"gentle", "steady", "stretch"}:
        difficulty = "gentle"
    return {"difficulty": str(difficulty), "kind": "general"}


def _audit(db: Session, actor: User, action: str, resource: str, dependent_id: UUID) -> None:
    db.add(AuditLog(actor_id=actor.id, action=action, resource_type=resource, dependent_id=dependent_id))


@router.get("/users/me")
def current_user(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    from app.api.v1.auth import to_user_out
    return to_user_out(db, current).model_dump(mode="json")


@router.get("/dependents/{dependent_id}/profile", response_model=ProfileOut)
def get_profile(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CareProfile:
    require_dependent_access(db, current, dependent_id, "profile")
    profile = db.scalar(select(CareProfile).where(CareProfile.user_id == dependent_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.add(AuditLog(actor_id=current.id, action="profile.read", resource_type="care_profile", resource_id=str(profile.id), dependent_id=dependent_id))
    db.commit()
    return profile


@router.put("/dependents/{dependent_id}/profile", response_model=ProfileOut)
def update_profile(dependent_id: UUID, payload: ProfileUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CareProfile:
    if current.id != dependent_id:
        raise HTTPException(status_code=403, detail="Only the dependent can update their own orientation settings")
    require_role(db, current, "DEPENDENT")
    profile = db.scalar(select(CareProfile).where(CareProfile.user_id == dependent_id))
    if profile is None:
        profile = CareProfile(user_id=dependent_id, preferred_name=payload.preferred_name)
        db.add(profile)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    _audit(db, current, "profile.update", "care_profile", dependent_id)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/dependents/{dependent_id}/medications", response_model=list[MedicationOut])
def list_medications(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Medication]:
    require_dependent_access(db, current, dependent_id, "routines")
    return list(db.scalars(select(Medication).where(Medication.dependent_id == dependent_id).order_by(Medication.created_at.desc())).all())


@router.post("/dependents/{dependent_id}/medications", response_model=MedicationOut, status_code=201)
def create_medication(dependent_id: UUID, payload: MedicationCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Medication:
    require_dependent_access(db, current, dependent_id, "routines")
    item = Medication(dependent_id=dependent_id, **payload.model_dump())
    db.add(item)
    db.flush()
    _audit(db, current, "medication.create", "medication", dependent_id)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/medications/{medication_id}", response_model=MedicationOut)
def update_medication(medication_id: UUID, payload: MedicationUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Medication:
    item = db.get(Medication, medication_id)
    if not item:
        raise HTTPException(status_code=404, detail="Medication not found")
    require_dependent_access(db, current, item.dependent_id, "routines")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/medications/{medication_id}", status_code=204)
def delete_medication(medication_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    item = db.get(Medication, medication_id)
    if not item:
        raise HTTPException(status_code=404, detail="Medication not found")
    require_dependent_access(db, current, item.dependent_id, "routines")
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.post("/medications/{medication_id}/events", status_code=201)
def medication_event(medication_id: UUID, event_type: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    item = db.get(Medication, medication_id)
    if not item:
        raise HTTPException(status_code=404, detail="Medication not found")
    require_dependent_access(db, current, item.dependent_id, "routines")
    if event_type not in {"taken", "skipped", "missed"}:
        raise HTTPException(status_code=422, detail="event_type must be taken, skipped, or missed")
    db.add(MedicationEvent(medication_id=item.id, actor_id=current.id, event_type=event_type))
    db.commit()
    return {"status": "recorded"}


@router.get("/dependents/{dependent_id}/appointments", response_model=list[AppointmentOut])
def list_appointments(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Appointment]:
    require_dependent_access(db, current, dependent_id, "routines")
    return list(db.scalars(select(Appointment).where(Appointment.dependent_id == dependent_id).order_by(Appointment.starts_at)).all())


@router.post("/dependents/{dependent_id}/appointments", response_model=AppointmentOut, status_code=201)
def create_appointment(dependent_id: UUID, payload: AppointmentCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Appointment:
    require_dependent_access(db, current, dependent_id, "routines")
    item = Appointment(dependent_id=dependent_id, **payload.model_dump())
    db.add(item)
    db.flush()
    _audit(db, current, "appointment.create", "appointment", dependent_id)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
def update_appointment(appointment_id: UUID, payload: AppointmentUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Appointment:
    item = db.get(Appointment, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Appointment not found")
    require_dependent_access(db, current, item.dependent_id, "routines")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/appointments/{appointment_id}", status_code=204)
def delete_appointment(appointment_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    item = db.get(Appointment, appointment_id)
    if not item:
        raise HTTPException(status_code=404, detail="Appointment not found")
    require_dependent_access(db, current, item.dependent_id, "routines")
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.get("/dependents/{dependent_id}/reminders", response_model=list[ReminderOut])
def list_reminders(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Reminder]:
    require_dependent_access(db, current, dependent_id, "routines")
    return list(db.scalars(select(Reminder).where(Reminder.dependent_id == dependent_id).order_by(Reminder.created_at.desc())).all())


@router.post("/dependents/{dependent_id}/reminders", response_model=ReminderOut, status_code=201)
def create_reminder(dependent_id: UUID, payload: ReminderCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Reminder:
    require_dependent_access(db, current, dependent_id, "routines")
    item = Reminder(dependent_id=dependent_id, **payload.model_dump())
    db.add(item)
    db.flush()
    _audit(db, current, "reminder.create", "reminder", dependent_id)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/reminders/{reminder_id}", response_model=ReminderOut)
def update_reminder(reminder_id: UUID, payload: ReminderUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Reminder:
    item = db.get(Reminder, reminder_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reminder not found")
    require_dependent_access(db, current, item.dependent_id, "routines")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/reminders/{reminder_id}", status_code=204)
def delete_reminder(reminder_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    item = db.get(Reminder, reminder_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reminder not found")
    require_dependent_access(db, current, item.dependent_id, "routines")
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.post("/reminders/{reminder_id}/events", status_code=201)
def reminder_event(reminder_id: UUID, event_type: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    item = db.get(Reminder, reminder_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reminder not found")
    require_dependent_access(db, current, item.dependent_id, "routines")
    if event_type not in {"completed", "snoozed", "skipped", "missed"}:
        raise HTTPException(status_code=422, detail="Invalid reminder event")
    db.add(ReminderEvent(reminder_id=item.id, actor_id=current.id, event_type=event_type))
    db.commit()
    return {"status": "recorded"}


@router.get("/dependents/{dependent_id}/emergency-contacts", response_model=list[EmergencyContactOut])
def list_emergency_contacts(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[EmergencyContact]:
    require_dependent_access(db, current, dependent_id, "emergency")
    return list(db.scalars(select(EmergencyContact).where(EmergencyContact.dependent_id == dependent_id).order_by(EmergencyContact.priority)).all())


@router.post("/dependents/{dependent_id}/emergency-contacts", response_model=EmergencyContactOut, status_code=201)
def create_emergency_contact(dependent_id: UUID, payload: EmergencyContactCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EmergencyContact:
    require_dependent_access(db, current, dependent_id, "emergency")
    item = EmergencyContact(dependent_id=dependent_id, **payload.model_dump())
    db.add(item)
    db.flush()
    _audit(db, current, "emergency_contact.create", "emergency_contact", dependent_id)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/emergency-contacts/{contact_id}", response_model=EmergencyContactOut)
def update_emergency_contact(contact_id: UUID, payload: EmergencyContactUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EmergencyContact:
    item = db.get(EmergencyContact, contact_id)
    if not item:
        raise HTTPException(status_code=404, detail="Emergency contact not found")
    require_dependent_access(db, current, item.dependent_id, "emergency")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/emergency-contacts/{contact_id}", status_code=204)
def delete_emergency_contact(contact_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    item = db.get(EmergencyContact, contact_id)
    if not item:
        raise HTTPException(status_code=404, detail="Emergency contact not found")
    require_dependent_access(db, current, item.dependent_id, "emergency")
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.get("/dependents/{dependent_id}/games", response_model=list[GameOut])
def list_games(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Game]:
    require_dependent_access(db, current, dependent_id, "profile")
    query = select(Game).where(Game.dependent_id == dependent_id)
    return list(db.scalars(query.order_by(Game.created_at.asc())).all())


@router.post("/dependents/{dependent_id}/games", response_model=GameOut, status_code=201)
def create_game(dependent_id: UUID, payload: GameCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Game:
    require_dependent_access(db, current, dependent_id, "profile")
    item = Game(
        dependent_id=dependent_id,
        title=GAME_TITLES[payload.game_type],
        game_type=payload.game_type,
        configuration=_safe_game_configuration(payload.configuration),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/games/{game_id}", response_model=GameOut)
def update_game(game_id: UUID, payload: GameUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Game:
    item = db.get(Game, game_id)
    if not item:
        raise HTTPException(status_code=404, detail="Game not found")
    require_dependent_access(db, current, item.dependent_id, "profile")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "title":
            continue
        if key == "configuration":
            value = _safe_game_configuration(value)
        setattr(item, key, value)
    item.title = GAME_TITLES[item.game_type]
    db.commit()
    db.refresh(item)
    return item


@router.delete("/games/{game_id}", status_code=204)
def delete_game(game_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    item = db.get(Game, game_id)
    if not item:
        raise HTTPException(status_code=404, detail="Game not found")
    require_dependent_access(db, current, item.dependent_id, "profile")
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.get("/dependents/{dependent_id}/alerts", response_model=list[AlertOut])
def list_alerts(dependent_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Alert]:
    require_dependent_access(db, current, dependent_id, "emergency")
    return list(db.scalars(select(Alert).where(Alert.dependent_id == dependent_id).order_by(Alert.created_at.desc()).limit(100)).all())


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Alert:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    require_dependent_access(db, current, alert.dependent_id, "emergency")
    alert.status = "acknowledged"
    alert.acknowledged_by = current.id
    alert.acknowledged_at = utc_now()
    _audit(db, current, "alert.acknowledge", "alert", alert.dependent_id)
    db.commit()
    db.refresh(alert)
    return alert
