from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.dependencies import get_current_user
from app.db.base import utc_now
from app.db.session import get_db
from app.models.entities import AuditLog, CareProfile, ConsentRecord, DataPermission, GuardianLink, User
from app.schemas.api import GuardianLinkOut, LinkAccept, LinkCreate, PermissionUpdate
from app.services.notifications import create_notification, mark_link_invitation_read
from app.services.authorization import has_role, require_role

router = APIRouter(tags=["guardian relationships"])


@router.post("/guardian/links", response_model=GuardianLinkOut, status_code=status.HTTP_201_CREATED)
def create_link(payload: LinkCreate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GuardianLink:
    require_role(db, current, "GUARDIAN")
    normalized_email = str(payload.dependent_email).strip().casefold()
    if normalized_email == current.email.casefold():
        raise HTTPException(status_code=400, detail="You cannot invite your own account.")
    dependent = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
    if dependent is None:
        raise HTTPException(status_code=404, detail="No registered dependent account was found with this email.")
    if has_role(db, dependent, "GUARDIAN"):
        raise HTTPException(status_code=400, detail="This email belongs to a guardian account.")
    if not has_role(db, dependent, "DEPENDENT"):
        raise HTTPException(status_code=404, detail="No registered dependent account was found with this email.")
    if not dependent.is_active:
        raise HTTPException(status_code=400, detail="This dependent account is inactive and cannot receive an invitation.")
    existing = db.scalar(select(GuardianLink).where(GuardianLink.guardian_id == current.id, GuardianLink.dependent_id == dependent.id))
    if existing and existing.status == "active":
        raise HTTPException(status_code=409, detail="This dependent is already linked to your account.")
    active_guardian = db.scalar(select(GuardianLink).where(
        GuardianLink.dependent_id == dependent.id,
        GuardianLink.status == "active",
    ).limit(1))
    if active_guardian:
        raise HTTPException(status_code=409, detail="This person already has an active guardian. The current guardian must revoke access before a new guardian can be connected.")
    if existing and existing.status == "pending":
        raise HTTPException(status_code=409, detail="An invitation is already pending for this account.")
    if existing:
        link = existing
        link.status = "pending"
        link.accepted_at = None
        link.declined_at = None
        link.revoked_at = None
        # Every re-connection requires the dependent to choose grants again.
        for permission in db.scalars(select(DataPermission).where(DataPermission.link_id == existing.id)).all():
            permission.allowed = False
    else:
        link = GuardianLink(guardian_id=current.id, dependent_id=dependent.id, status="pending")
    db.add(link)
    db.flush()
    db.add(AuditLog(actor_id=current.id, action="guardian_link.invite", resource_type="guardian_link", resource_id=str(link.id), dependent_id=dependent.id))
    create_notification(
        db,
        recipient_id=dependent.id,
        notification_type="guardian_link.invited",
        title="New care connection request",
        message=f"{current.display_name} wants to connect with you as your guardian/caregiver.",
        guardian_link_id=link.id,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An invitation already exists for this account.") from None
    db.refresh(link)
    return link


@router.get("/guardian/links", response_model=list[GuardianLinkOut])
def list_guardian_links(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[GuardianLink]:
    require_role(db, current, "GUARDIAN")
    return list(db.scalars(select(GuardianLink).where(GuardianLink.guardian_id == current.id).order_by(GuardianLink.created_at.desc())).all())


@router.get("/dependent/links")
def list_dependent_links(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    require_role(db, current, "DEPENDENT")
    links = db.scalars(select(GuardianLink).where(GuardianLink.dependent_id == current.id).order_by(GuardianLink.created_at.desc())).all()
    results = []
    for link in links:
        grants = db.scalars(select(DataPermission).where(DataPermission.link_id == link.id)).all()
        guardian = db.get(User, link.guardian_id)
        results.append({"id": str(link.id), "guardian_id": str(link.guardian_id), "guardian_name": guardian.display_name if guardian else "Guardian",
                       "status": link.status, "accepted_at": link.accepted_at, "declined_at": link.declined_at, "created_at": link.created_at,
                       "permissions": {grant.category: grant.allowed for grant in grants}})
    return results


@router.post("/dependent/links/{link_id}/accept", response_model=GuardianLinkOut)
def accept_link(link_id: UUID, payload: LinkAccept, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GuardianLink:
    require_role(db, current, "DEPENDENT")
    # Serialize accepts and revocations for the same dependent. The partial
    # unique index is the final guard if a caller bypasses this route.
    db.scalar(select(User.id).where(User.id == current.id).with_for_update())
    link = db.get(GuardianLink, link_id)
    if not link or link.dependent_id != current.id:
        raise HTTPException(status_code=404, detail="Link request not found")
    if link.status != "pending":
        raise HTTPException(status_code=409, detail="This link request is no longer pending")
    active_guardian = db.scalar(select(GuardianLink).where(
        GuardianLink.dependent_id == current.id,
        GuardianLink.status == "active",
        GuardianLink.id != link.id,
    ).limit(1))
    if active_guardian:
        raise HTTPException(status_code=409, detail="You already have an active guardian. Revoke that connection before accepting another request.")
    link.status = "active"
    link.accepted_at = utc_now()
    link.declined_at = None
    for permission in db.scalars(select(DataPermission).where(DataPermission.link_id == link.id)).all():
        permission.allowed = False
    for category in payload.granted_categories:
        permission = db.scalar(select(DataPermission).where(DataPermission.link_id == link.id, DataPermission.category == category))
        if permission:
            permission.allowed = True
            permission.granted_by = current.id
        else:
            db.add(DataPermission(link_id=link.id, category=category, allowed=True, granted_by=current.id))
    db.add(ConsentRecord(subject_id=current.id, actor_id=current.id, purpose="guardian_link", policy_version="1", granted=True))
    db.add(AuditLog(actor_id=current.id, action="guardian_link.accept", resource_type="guardian_link", resource_id=str(link.id), dependent_id=current.id))
    mark_link_invitation_read(db, recipient_id=current.id, link_id=link.id)
    create_notification(
        db,
        recipient_id=link.guardian_id,
        notification_type="guardian_link.accepted",
        title="Care connection approved",
        message=f"{current.display_name} accepted your care connection request.",
        guardian_link_id=link.id,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You already have an active guardian. Revoke that connection before accepting another request.") from None
    db.refresh(link)
    return link


@router.post("/dependent/links/{link_id}/decline", response_model=GuardianLinkOut)
def decline_link(link_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GuardianLink:
    require_role(db, current, "DEPENDENT")
    link = db.get(GuardianLink, link_id)
    if not link or link.dependent_id != current.id:
        raise HTTPException(status_code=404, detail="Link request not found")
    if link.status != "pending":
        raise HTTPException(status_code=409, detail="This link request is no longer pending")
    link.status = "declined"
    link.declined_at = utc_now()
    mark_link_invitation_read(db, recipient_id=current.id, link_id=link.id)
    db.add(AuditLog(actor_id=current.id, action="guardian_link.decline", resource_type="guardian_link", resource_id=str(link.id), dependent_id=current.id))
    create_notification(
        db,
        recipient_id=link.guardian_id,
        notification_type="guardian_link.declined",
        title="Care connection declined",
        message=f"{current.display_name} declined your care connection request.",
        guardian_link_id=link.id,
    )
    db.commit()
    db.refresh(link)
    return link


@router.put("/dependent/links/{link_id}/permissions", response_model=dict[str, bool])
def update_link_permissions(link_id: UUID, payload: PermissionUpdate, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, bool]:
    require_role(db, current, "DEPENDENT")
    link = db.get(GuardianLink, link_id)
    if not link or link.dependent_id != current.id or link.status != "active":
        raise HTTPException(status_code=404, detail="Active link not found")
    changed = False
    for category, allowed in payload.permissions.items():
        permission = db.scalar(select(DataPermission).where(DataPermission.link_id == link.id, DataPermission.category == category))
        if permission:
            if permission.allowed != allowed:
                permission.allowed = allowed
                permission.granted_by = current.id
                changed = True
        else:
            db.add(DataPermission(link_id=link.id, category=category, allowed=allowed, granted_by=current.id))
            changed = changed or allowed
    db.add(AuditLog(actor_id=current.id, action="guardian_link.permissions.update", resource_type="guardian_link", resource_id=str(link.id), dependent_id=current.id))
    if changed:
        create_notification(
            db,
            recipient_id=link.guardian_id,
            notification_type="guardian_link.permissions_changed",
            title="Sharing permissions changed",
            message=f"{current.display_name} updated the information you can access.",
            guardian_link_id=link.id,
        )
    db.commit()
    return payload.permissions


@router.post("/dependent/links/{link_id}/revoke", response_model=GuardianLinkOut)
def revoke_link(link_id: UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GuardianLink:
    require_role(db, current, "DEPENDENT")
    db.scalar(select(User.id).where(User.id == current.id).with_for_update())
    link = db.get(GuardianLink, link_id)
    if not link or link.dependent_id != current.id or link.status != "active":
        raise HTTPException(status_code=404, detail="Active link not found")
    link.status = "revoked"
    link.revoked_at = utc_now()
    for permission in db.scalars(select(DataPermission).where(DataPermission.link_id == link.id)).all():
        permission.allowed = False
    db.add(AuditLog(actor_id=current.id, action="guardian_link.revoke", resource_type="guardian_link", resource_id=str(link.id), dependent_id=current.id))
    create_notification(
        db,
        recipient_id=link.guardian_id,
        notification_type="guardian_link.revoked",
        title="Care connection access revoked",
        message=f"{current.display_name} revoked your access to their shared information.",
        guardian_link_id=link.id,
    )
    db.commit()
    db.refresh(link)
    return link


@router.get("/guardian/dependents", response_model=list[dict[str, object]])
def linked_dependents(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    require_role(db, current, "GUARDIAN")
    conflicted_dependents = set(db.scalars(
        select(GuardianLink.dependent_id)
        .where(GuardianLink.status == "active")
        .group_by(GuardianLink.dependent_id)
        .having(func.count(GuardianLink.id) > 1)
    ).all())
    links = db.scalars(select(GuardianLink).where(GuardianLink.guardian_id == current.id, GuardianLink.status == "active")).all()
    results: list[dict[str, object]] = []
    for link in links:
        if link.dependent_id in conflicted_dependents:
            continue
        dependent = db.get(User, link.dependent_id)
        profile = db.scalar(select(CareProfile).where(CareProfile.user_id == link.dependent_id))
        grants = db.scalars(select(DataPermission).where(DataPermission.link_id == link.id, DataPermission.allowed.is_(True))).all()
        allowed_categories = sorted(item.category for item in grants)
        profile_allowed = "profile" in allowed_categories
        results.append({
            "id": str(dependent.id),
            "display_name": dependent.display_name if profile_allowed else "Linked dependent",
            "preferred_name": (profile.preferred_name if profile else dependent.display_name) if profile_allowed else None,
            "permissions": allowed_categories,
        })
    return results
