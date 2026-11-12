import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.entities import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = decode_access_token(credentials.credentials)
        user = db.get(User, UUID(claims.get("sub", "")))
        if not user or not user.is_active or claims.get("ver") != user.token_version:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked token", headers={"WWW-Authenticate": "Bearer"})
        return user
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}) from None
