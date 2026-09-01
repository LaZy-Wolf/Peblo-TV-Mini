from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_token, current_user, verify_password
from app.db import get_session
from app.errors import ApiError, ApiException
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    role: str
    email: str


class MeResponse(BaseModel):
    id: int
    email: str
    role: str


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = session.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise ApiException(
            401,
            [ApiError("invalid_credentials", "That email and password do not match.")],
        )
    return TokenResponse(access_token=create_token(user), role=str(user.role), email=user.email)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(current_user)) -> MeResponse:
    return MeResponse(id=user.id, email=user.email, role=str(user.role))
