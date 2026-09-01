from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness only.

    Deliberately touches no dependency, so a database blip does not cause the
    orchestrator to kill an otherwise healthy container.
    """
    return {"status": "ok"}
