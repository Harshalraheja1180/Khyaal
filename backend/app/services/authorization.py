from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import DataPermission, GuardianLink, User, UserRole


def role_names(db: Session, user: User) -> list[str]:
    return list(db.scalars(select(UserRole).where(UserRole.user_id == user.id)).all() and db.scalars(
        select(__import__("app.models.entities", fromlist=["Role"]).Role.name)
        .join(UserRole, UserRole.role_id == __import__("app.models.entities", fromlist=["Role"]).Role.id)
        .where(UserRole.user_id == user.id)
    ).all())


def has_role(db: Session, user: User, role_name: str) -> bool:
    from app.models.entities import Role

    return db.scalar(
        select(Role.id).join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id, Role.name == role_name)
    ) is not None


def require_role(db: Session, user: User, role_name: str) -> None:
    if not has_role(db, user, role_name):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account does not have the required role")


def require_dependent_access(db: Session, actor: User, dependent_id: UUID, category: str) -> None:
    if actor.id == dependent_id:
        require_role(db, actor, "DEPENDENT")
        return
    require_role(db, actor, "GUARDIAN")
    active_guardian_count = db.scalar(select(func.count(GuardianLink.id)).where(
        GuardianLink.dependent_id == dependent_id,
        GuardianLink.status == "active",
    )) or 0
    if active_guardian_count > 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This care connection needs review. Access is paused until the dependent resolves multiple active guardian links.")
    link = db.scalar(select(GuardianLink).where(
        GuardianLink.guardian_id == actor.id,
        GuardianLink.dependent_id == dependent_id,
        GuardianLink.status == "active",
    ))
    if not link:
        raise HTTPException(status_code=404, detail="Dependent not found")
    permission = db.scalar(select(DataPermission).where(
        DataPermission.link_id == link.id,
        DataPermission.category == category,
        DataPermission.allowed.is_(True),
    ))
    if not permission:
        raise HTTPException(status_code=403, detail="This guardian has not been granted this data category")
