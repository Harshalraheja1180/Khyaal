from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    role: Literal["GUARDIAN", "DEPENDENT"] = "GUARDIAN"
    mode: Literal["OLDER_ADULT", "MEMORY_SUPPORT"] = "OLDER_ADULT"

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().casefold() if isinstance(value, str) else value

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Display name cannot be blank")
        return value.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    role: Literal["GUARDIAN", "DEPENDENT"] | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().casefold() if isinstance(value, str) else value


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChangeRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirmation do not match")
        if self.current_password == self.new_password:
            raise ValueError("Choose a new password different from your current password")
        return self


class UserOut(ORMModel):
    id: UUID
    email: EmailStr
    display_name: str
    roles: list[str]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class LinkCreate(BaseModel):
    dependent_email: EmailStr

    @field_validator("dependent_email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().casefold() if isinstance(value, str) else value


class LinkAccept(BaseModel):
    granted_categories: list[Literal["profile", "routines", "emergency", "media", "reports", "wellbeing", "location"]] = Field(default_factory=list)


class PermissionUpdate(BaseModel):
    permissions: dict[Literal["profile", "routines", "emergency", "media", "reports", "wellbeing", "location"], bool]


class GuardianLinkOut(ORMModel):
    id: UUID
    guardian_id: UUID
    dependent_id: UUID
    status: str
    accepted_at: datetime | None
    declined_at: datetime | None = None
    created_at: datetime


class NotificationOut(ORMModel):
    id: UUID
    notification_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    guardian_link_id: UUID | None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_name: str = Field(min_length=1, max_length=120)
    mode: Literal["OLDER_ADULT", "MEMORY_SUPPORT"] = "OLDER_ADULT"
    timezone: str = Field(default="UTC", max_length=80)
    locale: str = Field(default="en", max_length=16)
    age_band: str | None = Field(default=None, max_length=24)


class ProfileOut(ORMModel):
    id: UUID
    user_id: UUID
    preferred_name: str
    mode: str
    timezone: str
    locale: str
    age_band: str | None


class MedicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    instructions: str | None = Field(default=None, max_length=1000)
    schedule: dict[str, Any] = Field(default_factory=dict)


class MedicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    instructions: str | None = Field(default=None, max_length=1000)
    schedule: dict[str, Any] | None = None
    active: bool | None = None


class MedicationOut(ORMModel):
    id: UUID
    dependent_id: UUID
    name: str
    instructions: str | None
    schedule: dict[str, Any]
    active: bool


class AppointmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    starts_at: datetime
    location_label: str | None = Field(default=None, max_length=240)
    notes: str | None = Field(default=None, max_length=2000)


class AppointmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    starts_at: datetime | None = None
    location_label: str | None = Field(default=None, max_length=240)
    notes: str | None = Field(default=None, max_length=2000)


class AppointmentOut(ORMModel):
    id: UUID
    dependent_id: UUID
    title: str
    starts_at: datetime
    location_label: str | None
    notes: str | None


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    kind: str = Field(default="custom", min_length=1, max_length=32)
    schedule: dict[str, Any] = Field(default_factory=dict)


class ReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    kind: str | None = Field(default=None, min_length=1, max_length=32)
    schedule: dict[str, Any] | None = None
    active: bool | None = None


class ReminderOut(ORMModel):
    id: UUID
    dependent_id: UUID
    title: str
    kind: str
    schedule: dict[str, Any]
    active: bool


class EmergencyContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relationship_label: str = Field(default="trusted contact", max_length=80)
    phone: str = Field(min_length=5, max_length=40)
    priority: int = Field(default=1, ge=1, le=20)


class EmergencyContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    relationship_label: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, min_length=5, max_length=40)
    priority: int | None = Field(default=None, ge=1, le=20)


class EmergencyContactOut(ORMModel):
    id: UUID
    dependent_id: UUID
    name: str
    relationship_label: str
    phone: str
    priority: int


class QuizCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    difficulty: Literal["gentle", "steady", "stretch"] = "gentle"


class QuizQuestionCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    position: int = Field(default=0, ge=0)
    image_media_id: UUID | None = None
    audio_media_id: UUID | None = None


class QuizQuestionUpdate(BaseModel):
    prompt: str | None = Field(default=None, min_length=1, max_length=500)
    position: int | None = Field(default=None, ge=0)
    image_media_id: UUID | None = None
    audio_media_id: UUID | None = None


class QuizOptionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=240)
    is_correct: bool = False
    position: int = Field(default=0, ge=0)
    image_media_id: UUID | None = None


class QuizOptionUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=240)
    is_correct: bool | None = None
    position: int | None = Field(default=None, ge=0)
    image_media_id: UUID | None = None


class QuizAnswerCreate(BaseModel):
    option_id: UUID


class GameCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    game_type: Literal["sequence_memory", "tile_memory", "pattern_memory", "matching_pairs", "odd_one_out"]
    configuration: dict[str, Any] = Field(default_factory=dict)


class MemoryEntryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    relationship_label: str | None = Field(default=None, max_length=80)
    media_id: UUID | None = None


class MemoryEntryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    relationship_label: str | None = Field(default=None, max_length=80)
    media_id: UUID | None = None


class QuizUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    difficulty: Literal["gentle", "steady", "stretch"] | None = None
    active: bool | None = None


class GameUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    game_type: Literal["sequence_memory", "tile_memory", "pattern_memory", "matching_pairs", "odd_one_out"] | None = None
    configuration: dict[str, Any] | None = None
    active: bool | None = None


class WellbeingCheckinCreate(BaseModel):
    answers: dict[str, str] = Field(min_length=1, max_length=20)


class GameSessionStart(BaseModel):
    game_type: Literal["sequence_memory", "tile_memory", "pattern_memory", "matching_pairs", "odd_one_out"]


class AlertOut(ORMModel):
    id: UUID
    dependent_id: UUID
    alert_type: str
    severity: str
    status: str
    message: str
    acknowledged_by: UUID | None
    acknowledged_at: datetime | None


class QuizOut(ORMModel):
    id: UUID
    dependent_id: UUID
    title: str
    difficulty: str
    active: bool


class LocationPermissionUpdate(BaseModel):
    enabled: bool
    purpose: str = Field(default="", max_length=240)
    retention_days: int = Field(default=7, ge=1, le=90)


class LocationCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class GameSessionFinish(BaseModel):
    interactions: int = Field(ge=0, le=10000)
    result: dict[str, Any] = Field(default_factory=dict)


class GameOut(ORMModel):
    id: UUID
    dependent_id: UUID
    title: str
    game_type: str
    configuration: dict[str, Any]
    active: bool


class MessageOut(BaseModel):
    message: str
