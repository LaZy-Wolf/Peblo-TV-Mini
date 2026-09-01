from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_editor
from app.db import get_session
from app.models import User
from app.validation import build_validation_report

router = APIRouter(prefix="/admin", tags=["catalog-admin"])


@router.get("/validation-report")
def validation_report(
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    return asdict(build_validation_report(session))
