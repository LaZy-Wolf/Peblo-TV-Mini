from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_admin, require_editor
from app.catalog.publish import PublishBlocked, publish, rollback
from app.catalog.serve import invalidate_cache
from app.db import get_session
from app.models import PublishRun, User
from app.storage import get_storage
from app.validation import build_validation_report

router = APIRouter(prefix="/admin", tags=["catalog-admin"])


@router.get("/validation-report")
def validation_report(
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    return asdict(build_validation_report(session))


def _run_out(run: PublishRun) -> dict:
    return {
        "id": run.id,
        "run_id": str(run.run_id),
        "status": run.status,
        "started_by": run.started_by,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "counts": run.counts,
        "catalog_key": run.catalog_key,
        "content_hash": run.content_hash,
        "error": run.error,
    }


@router.post("/catalog/publish")
def publish_catalog(
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
):
    try:
        run = publish(session, get_storage(), user.id)
    except PublishBlocked as blocked:
        # 409 rather than 422: the request was well formed, the catalogue is
        # simply not in a publishable state yet.
        return JSONResponse(
            status_code=409,
            content={
                "errors": [
                    {
                        "code": "publish_blocked",
                        "message": (
                            f"{blocked.report['blocking_count']} problems need fixing "
                            "before this catalogue can go live."
                        ),
                        "field": None,
                    }
                ],
                "report": blocked.report,
            },
        )
    invalidate_cache()
    return _run_out(run)


class RollbackRequest(BaseModel):
    run_db_id: int


@router.post("/catalog/rollback")
def rollback_catalog(
    body: RollbackRequest,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> dict:
    run = rollback(session, get_storage(), body.run_db_id)
    invalidate_cache()
    return _run_out(run)


@router.get("/catalog/runs")
def list_runs(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    runs = session.scalars(
        select(PublishRun).order_by(PublishRun.started_at.desc(), PublishRun.id.desc()).limit(limit)
    ).all()
    return {"items": [_run_out(r) for r in runs]}
