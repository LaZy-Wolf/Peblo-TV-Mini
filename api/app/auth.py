from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.errors import ApiError, ApiException
from app.models import Role, User

_scheme = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": str(user.role),
        "exp": datetime.now(UTC) + timedelta(hours=settings.jwt_expiry_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _unauthorized() -> ApiException:
    return ApiException(401, [ApiError("not_authenticated", "Please sign in to continue.")])


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_scheme),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise _unauthorized()
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise _unauthorized() from exc
    user = session.get(User, int(payload["sub"]))
    if user is None:
        raise _unauthorized()
    return user


def require_editor(user: User = Depends(current_user)) -> User:
    """Both roles may read and write content."""
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if str(user.role) != Role.admin:
        raise ApiException(
            403,
            [
                ApiError(
                    "forbidden",
                    "Publishing is restricted to administrators. Ask an administrator to "
                    "publish, or request admin access.",
                )
            ],
        )
    return user
