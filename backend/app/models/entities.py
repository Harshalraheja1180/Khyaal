from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, LargeBinary, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, utc_now


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(180), default="", nullable=False)


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(180), default="", nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class User(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class GuardianLink(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "guardian_links"
    __table_args__ = (
        UniqueConstraint("guardian_id", "dependent_id", name="uq_guardian_dependent_pair"),
        Index(
            "uq_guardian_links_one_active_per_dependent",
            "dependent_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DataPermission(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "data_permissions"
    __table_args__ = (UniqueConstraint("link_id", "category", name="uq_link_permission_category"),)
    link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("guardian_links.id", ondelete="CASCADE"), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    granted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class CareProfile(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "care_profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    preferred_name: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="OLDER_ADULT", nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC", nullable=False)
    locale: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    age_band: Mapped[str | None] = mapped_column(String(24))


class AccessibilityPreference(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "accessibility_preferences"
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("care_profiles.id", ondelete="CASCADE"), unique=True, nullable=False)
    text_scale: Mapped[str] = mapped_column(String(20), default="large", nullable=False)
    high_contrast: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_aloud: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reduced_motion: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Medication(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "medications"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    schedule: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MedicationEvent(Base, UUIDPrimaryKey):
    __tablename__ = "medication_events"
    medication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("medications.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))


class Appointment(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "appointments"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    location_label: Mapped[str | None] = mapped_column(String(240))
    notes: Mapped[str | None] = mapped_column(Text)


class Reminder(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "reminders"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="custom", nullable=False)
    schedule: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ReminderEvent(Base, UUIDPrimaryKey):
    __tablename__ = "reminder_events"
    reminder_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class EmergencyContact(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "emergency_contacts"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    relationship_label: Mapped[str] = mapped_column(String(80), default="trusted contact", nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class MemoryProfile(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "memory_profiles"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    introduction: Mapped[str | None] = mapped_column(Text)


class MediaAsset(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "media_assets"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="photo", nullable=False)


class MemoryPerson(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "memory_people"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    relationship_label: Mapped[str | None] = mapped_column(String(80))
    media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))


class MemoryPlace(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "memory_places"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))


class MemoryObject(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "memory_objects"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))


class OrientationActivity(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "orientation_activities"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt: Mapped[str] = mapped_column(String(500), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Quiz(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "quizzes"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(24), default="gentle", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class QuizQuestion(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "quiz_questions"
    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True, nullable=False)
    prompt: Mapped[str] = mapped_column(String(500), nullable=False)
    image_media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))
    audio_media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class QuizOption(Base, UUIDPrimaryKey):
    __tablename__ = "quiz_options"
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quiz_questions.id", ondelete="CASCADE"), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    image_media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class QuizAttempt(Base, UUIDPrimaryKey):
    __tablename__ = "quiz_attempts"
    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True, nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quiz_questions.id", ondelete="CASCADE"), index=True, nullable=False)
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    selected_option_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quiz_options.id", ondelete="SET NULL"))
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Game(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "games"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    game_type: Mapped[str] = mapped_column(String(32), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GameSession(Base, UUIDPrimaryKey):
    __tablename__ = "game_sessions"
    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True, nullable=False)
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class WellbeingCheckin(Base, UUIDPrimaryKey):
    __tablename__ = "wellbeing_checkins"
    __table_args__ = (Index(
        "uq_wellbeing_dependent_date_active",
        "dependent_id",
        "checkin_date",
        unique=True,
        postgresql_where=text("reset_at IS NULL"),
        sqlite_where=text("reset_at IS NULL"),
    ),)
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # Nullable for legacy check-ins created before daily completion was introduced.
    checkin_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    overall_category: Mapped[str | None] = mapped_column(String(40))
    category_scores: Mapped[dict[str, int] | None] = mapped_column(JSON)
    summary: Mapped[str | None] = mapped_column(Text)
    declined: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Alert(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "alerts"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    alert_type: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LocationPermission(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "location_permissions"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    purpose: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)


class LocationEvent(Base, UUIDPrimaryKey):
    __tablename__ = "location_events"
    dependent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ConsentRecord(Base, UUIDPrimaryKey):
    __tablename__ = "consents"
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Notification(Base, UUIDPrimaryKey):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_unread", "user_id", "is_read"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    guardian_link_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("guardian_links.id", ondelete="SET NULL"), index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AuditLog(Base, UUIDPrimaryKey):
    __tablename__ = "audit_logs"
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    dependent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    outcome: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


Index("ix_game_sessions_dependent_started", GameSession.dependent_id, GameSession.started_at)
Index("ix_alerts_dependent_status", Alert.dependent_id, Alert.status)
Index("ix_location_events_dependent_recorded", LocationEvent.dependent_id, LocationEvent.recorded_at)
