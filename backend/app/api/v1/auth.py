from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.base import utc_now
from app.db.session import get_db
from app.models.entities import AuditLog, CareProfile, Role, User, UserRole
from app.schemas.api import LoginRequest, MessageOut, PasswordChangeRequest, RegisterRequest, TokenOut, UserOut
from app.services.authorization import has_role, role_names

router = APIRouter(prefix="/auth", tags=["authentication"])


def to_user_out(db: Session, user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, display_name=user.display_name, roles=role_names(db, user))


def issue_token(db: Session, user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(str(user.id), user.token_version), expires_in=settings.access_token_minutes * 60, user=to_user_out(db, user))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenOut:
    email = str(payload.email).lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    role = db.scalar(select(Role).where(Role.name == payload.role))
    if role is None:
        raise HTTPException(status_code=503, detail="Role configuration is missing; run the seed/bootstrap command")
    user = User(email=email, password_hash=hash_password(payload.password), display_name=payload.display_name.strip())
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.add(AuditLog(actor_id=user.id, action="auth.register", resource_type="user", resource_id=str(user.id)))
    if payload.role == "DEPENDENT":
        db.add(CareProfile(user_id=user.id, preferred_name=user.display_name, mode=payload.mode))
    db.commit()
    db.refresh(user)
    return issue_token(db, user)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == str(payload.email).casefold()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    if payload.role and not has_role(db, user, payload.role):
        role_label = "guardian" if payload.role == "GUARDIAN" else "dependent"
        raise HTTPException(status_code=403, detail=f"This account is not registered as a {role_label}.")
    db.add(AuditLog(actor_id=user.id, action="auth.login", resource_type="user", resource_id=str(user.id)))
    db.commit()
    return issue_token(db, user)


@router.post("/logout", response_model=MessageOut)
def logout(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageOut:
    current.token_version += 1
    current.updated_at = utc_now()
    db.add(AuditLog(actor_id=current.id, action="auth.logout", resource_type="user", resource_id=str(current.id)))
    db.commit()
    return MessageOut(message="All active access tokens for this account have been revoked")


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    return to_user_out(db, current)


@router.post("/change-password", response_model=MessageOut)
def change_password(
    payload: PasswordChangeRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    if not verify_password(payload.current_password, current.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current.password_hash = hash_password(payload.new_password)
    current.token_version += 1
    current.updated_at = utc_now()
    db.add(AuditLog(actor_id=current.id, action="auth.password_change", resource_type="user", resource_id=str(current.id)))
    db.commit()
    return MessageOut(message="Password changed. Please sign in again with your new password.")
