from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.catalog.serve import current_catalog
from app.db import get_session
from app.storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness only.

    Deliberately touches no dependency, so a database blip does not cause the
    orchestrator to kill an otherwise healthy container.
    """
    return {"status": "ok"}


@router.get("/readyz")
def readyz(session: Session = Depends(get_session)) -> JSONResponse:
    """Readiness, which unlike liveness is allowed to fail on a dependency.

    The catalog check is the interesting one: it proves the pointer resolves
    to a file that actually reads, which is the exact state the viewer needs.
    """
    checks = {"database": False, "storage": False, "catalog": False}

    try:
        session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    storage = get_storage()
    try:
        storage.exists("readyz-probe")
        checks["storage"] = True
    except Exception:
        pass

    try:
        checks["catalog"] = current_catalog(session, storage) is not None
    except Exception:
        pass

    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "degraded", "checks": checks},
    )
