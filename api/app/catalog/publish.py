"""Publishing.

Every run writes a file at a key nothing has ever used, then flips a single
row to point at it. That pointer update is the atomic commit point: before it
the new file is unreachable, after it every reader sees the complete file.
Nothing ever overwrites the live catalogue.
"""

import json
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.build import build_catalog, content_hash, serialise
from app.errors import ApiError, ApiException
from app.models import CatalogPointer, PublishRun, RunStatus
from app.storage.base import Storage
from app.validation import build_validation_report

STALE_RUN_MINUTES = 5


class PublishBlocked(Exception):
    def __init__(self, run: PublishRun, report: dict):
        self.run = run
        self.report = report
        super().__init__("publish blocked by validation")


def _counts(catalog: dict) -> dict:
    shows = [s for section in catalog["sections"] for s in section["shows"]]
    episodes = [e for s in shows for season in s["seasons"] for e in season["episodes"]]
    trailers = [t for s in shows for t in s["trailers"]]
    return {
        "shows": len(shows),
        "episodes": len(episodes),
        "trailers": len(trailers),
        "sections": len([s for s in catalog["sections"] if s["shows"]]),
    }


def _flip_pointer(session: Session, run: PublishRun) -> None:
    """The atomic commit point.

    Extracted as its own function so a test can make it fail and prove that a
    crash here leaves readers on the previous catalogue.
    """
    pointer = session.get(CatalogPointer, 1)
    if pointer is None:
        pointer = CatalogPointer(id=1)
        session.add(pointer)
    pointer.current_run_id = run.id
    session.flush()


def _current_run(session: Session) -> PublishRun | None:
    pointer = session.get(CatalogPointer, 1)
    if pointer is None or pointer.current_run_id is None:
        return None
    return session.get(PublishRun, pointer.current_run_id)


def publish(session: Session, storage: Storage, user_id: int | None) -> PublishRun:
    run_id = uuid.uuid4()
    run = PublishRun(run_id=run_id, started_by=user_id, status=RunStatus.running)
    session.add(run)
    session.flush()

    report = build_validation_report(session)
    if not report.can_publish:
        run.status = RunStatus.failed
        run.finished_at = datetime.now(UTC)
        run.error = {"blocking_count": report.blocking_count}
        session.flush()
        raise PublishBlocked(run, asdict(report))

    catalog = build_catalog(session, run_id)
    digest = content_hash(catalog)
    run.content_hash = digest

    current = _current_run(session)
    if current is not None and current.content_hash == digest:
        # Nothing changed. Recording the run without writing is what makes
        # publish idempotent: two publishes over unchanged data leave one file.
        run.status = RunStatus.no_change
        run.finished_at = datetime.now(UTC)
        run.counts = _counts(catalog)
        session.flush()
        return run

    key = f"catalog/runs/{run_id}.json"
    storage.put(key, serialise(catalog), "application/json")

    # A write that reported success but landed corrupt must not become live.
    if content_hash(json.loads(storage.get(key))) != digest:
        run.status = RunStatus.failed
        run.finished_at = datetime.now(UTC)
        run.error = {"message": "The catalogue file did not read back correctly."}
        session.flush()
        raise RuntimeError("catalogue verification failed after write")

    run.catalog_key = key
    _flip_pointer(session, run)
    run.status = RunStatus.success
    run.counts = _counts(catalog)
    run.finished_at = datetime.now(UTC)
    session.flush()
    return run


def rollback(session: Session, storage: Storage, run_db_id: int) -> PublishRun:
    """Point the catalogue at an earlier successful run.

    This is a handful of lines rather than a project because publishing never
    overwrites, so every previous catalogue file is still exactly where it was.
    """
    target = session.get(PublishRun, run_db_id)
    if target is None or target.status != RunStatus.success or not target.catalog_key:
        raise ApiException(
            422,
            [
                ApiError(
                    "rollback_invalid_target",
                    "You can only roll back to a publish that finished successfully.",
                    "run_db_id",
                )
            ],
        )
    if not storage.exists(target.catalog_key):
        raise ApiException(
            422,
            [
                ApiError(
                    "rollback_file_missing",
                    "That catalogue file is no longer in storage, so we cannot roll back to it.",
                    "run_db_id",
                )
            ],
        )
    _flip_pointer(session, target)
    return target


def sweep_stale_runs(session: Session) -> int:
    """Mark runs abandoned by a dead process.

    Without this, a publish that died mid-flight shows as permanently spinning
    in run history and nobody can tell it never finished.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=STALE_RUN_MINUTES)
    stale = session.scalars(
        select(PublishRun).where(
            PublishRun.status == RunStatus.running, PublishRun.started_at < cutoff
        )
    ).all()
    for run in stale:
        run.status = RunStatus.failed
        run.finished_at = datetime.now(UTC)
        run.error = {"message": "This publish did not finish. It was probably interrupted."}
    session.flush()
    return len(stale)
