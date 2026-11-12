from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.entities import (
    Appointment, CareProfile, EmergencyContact, Game, GuardianLink, Medication, MemoryObject,
    MemoryPerson, MemoryPlace, Permission, Quiz, QuizOption, QuizQuestion, Reminder, Role,
    RolePermission, User, UserRole,
)

ROLES = {
    "ADMIN": "Platform support without default private-data access",
    "GUARDIAN": "Caregiver with explicitly granted dependent scopes",
    "DEPENDENT": "Person receiving care and controlling relationship grants",
}
PERMISSIONS = {
    "users.read": "Read own user identity",
    "links.manage": "Manage own guardian relationship requests",
    "care.read": "Read permitted routine and profile data",
    "care.write": "Write permitted routine and profile data",
    "media.read": "Read private media after scope authorization",
    "media.write": "Upload private media after scope authorization",
    "support.manage": "Administrative support configuration",
}


def ensure_access_catalog(db: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for name, description in ROLES.items():
        role = db.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(name=name, description=description)
            db.add(role)
            db.flush()
        roles[name] = role
    permissions: dict[str, Permission] = {}
    for code, description in PERMISSIONS.items():
        permission = db.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, description=description)
            db.add(permission)
            db.flush()
        permissions[code] = permission
    assignments = {
        "ADMIN": ["users.read", "support.manage"],
        "GUARDIAN": ["users.read", "links.manage", "care.read", "care.write", "media.read", "media.write"],
        "DEPENDENT": list(PERMISSIONS.keys())[:-1],
    }
    for role_name, codes in assignments.items():
        for code in codes:
            exists = db.get(RolePermission, (roles[role_name].id, permissions[code].id))
            if exists is None:
                db.add(RolePermission(role_id=roles[role_name].id, permission_id=permissions[code].id))
    db.flush()
    return roles


def get_or_create_user(db: Session, email: str, name: str, role_name: str, password_hash: str, roles: dict[str, Role]) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, display_name=name, password_hash=password_hash)
        db.add(user)
        db.flush()
    if db.get(UserRole, (user.id, roles[role_name].id)) is None:
        db.add(UserRole(user_id=user.id, role_id=roles[role_name].id))
    return user


def seed_demo(db: Session, demo_password: str) -> None:
    roles = ensure_access_catalog(db)
    password_hash = hash_password(demo_password)
    admin = get_or_create_user(db, "admin@memorycare.example.com", "Alex Admin (Demo)", "ADMIN", password_hash, roles)
    guardian = get_or_create_user(db, "guardian@memorycare.example.com", "Jordan Caregiver (Demo)", "GUARDIAN", password_hash, roles)
    older = get_or_create_user(db, "meera.demo@memorycare.example.com", "Meera Example (Demo)", "DEPENDENT", password_hash, roles)
    support = get_or_create_user(db, "aarav.demo@memorycare.example.com", "Aarav Example (Demo)", "DEPENDENT", password_hash, roles)
    db.flush()

    for user, mode in ((older, "OLDER_ADULT"), (support, "MEMORY_SUPPORT")):
        profile = db.scalar(select(CareProfile).where(CareProfile.user_id == user.id))
        if profile is None:
            db.add(CareProfile(user_id=user.id, preferred_name=user.display_name.split()[0], mode=mode, timezone="Asia/Calcutta"))
    from app.models.entities import DataPermission
    for dependent in (older, support):
        link = db.scalar(select(GuardianLink).where(GuardianLink.guardian_id == guardian.id, GuardianLink.dependent_id == dependent.id))
        if link is None:
            link = GuardianLink(guardian_id=guardian.id, dependent_id=dependent.id, status="active")
            db.add(link)
            db.flush()
        else:
            link.status = "active"
            link.revoked_at = None
        for category in ("profile", "routines", "emergency", "media", "reports", "wellbeing"):
            permission = db.scalar(select(DataPermission).where(DataPermission.link_id == link.id, DataPermission.category == category))
            if permission is None:
                db.add(DataPermission(link_id=link.id, category=category, allowed=True, granted_by=dependent.id))
            else:
                permission.allowed = True

    db.flush()
    if not db.scalar(select(Medication.id).where(Medication.dependent_id == older.id, Medication.name == "Demo vitamin")):
        db.add(Medication(dependent_id=older.id, name="Demo vitamin", instructions="Fictional example only", schedule={"times": ["09:00"], "days": ["daily"]}))
    if not db.scalar(select(Reminder.id).where(Reminder.dependent_id == older.id, Reminder.title == "Demo morning walk")):
        db.add(Reminder(dependent_id=older.id, title="Demo morning walk", kind="exercise", schedule={"time": "08:30", "days": ["mon", "wed", "fri"]}))
    if not db.scalar(select(Appointment.id).where(Appointment.dependent_id == older.id, Appointment.title == "Demo community visit")):
        from datetime import datetime, timedelta, timezone
        db.add(Appointment(dependent_id=older.id, title="Demo community visit", starts_at=datetime.now(timezone.utc) + timedelta(days=3), location_label="Example Community Center"))
    if not db.scalar(select(EmergencyContact.id).where(EmergencyContact.dependent_id == older.id, EmergencyContact.name == "Taylor Example")):
        db.add(EmergencyContact(dependent_id=older.id, name="Taylor Example", relationship_label="Trusted friend", phone="+1-202-555-0142", priority=1))
    demo_memories = [
        (MemoryPerson, support, "Riya Example", {"relationship_label": "Niece"}),
        (MemoryPlace, support, "Example family home", {"description": "A familiar place in the demo"}),
        (MemoryObject, support, "Blue mug", {"description": "A familiar household object"}),
        (MemoryPlace, older, "Example family home", {"description": "Home in this fictional demo"}),
    ]
    for model, dependent, name, extra in demo_memories:
        if not db.scalar(select(model.id).where(model.dependent_id == dependent.id, model.name == name)):
            db.add(model(dependent_id=dependent.id, name=name, **extra))
    quiz = db.scalar(select(Quiz).where(Quiz.dependent_id == support.id, Quiz.title == "Demo familiar places"))
    if quiz is None:
        quiz = Quiz(dependent_id=support.id, title="Demo familiar places")
        db.add(quiz)
        db.flush()
        question = QuizQuestion(quiz_id=quiz.id, prompt="Which picture shows the example home?", position=1)
        db.add(question)
        db.flush()
        db.add_all([
            QuizOption(question_id=question.id, label="Example home", is_correct=True, position=1),
            QuizOption(question_id=question.id, label="Example garden", is_correct=False, position=2),
        ])
    general_games = [
        ("sequence_memory", "Sequence Memory"),
        ("tile_memory", "Tile Memory"),
        ("pattern_memory", "Pattern Memory"),
        ("matching_pairs", "Matching Pairs"),
        ("odd_one_out", "Odd One Out"),
    ]
    for dependent in (older, support):
        for game_type, title in general_games:
            if not db.scalar(select(Game.id).where(Game.dependent_id == dependent.id, Game.game_type == game_type)):
                db.add(Game(dependent_id=dependent.id, title=title, game_type=game_type, configuration={"difficulty": "gentle", "kind": "general"}))
    db.flush()
