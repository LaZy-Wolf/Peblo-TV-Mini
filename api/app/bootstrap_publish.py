"""Publish an initial catalogue at container start.

Idempotent by the hash rule in catalog.publish, so a restart records a
no_change run rather than writing a second identical file. Never fails the
container: if validation blocks, the API still starts and the CMS shows the
editor exactly what to fix.
"""

import logging
import sys

from app.catalog.publish import PublishBlocked, publish
from app.db import SessionLocal
from app.models import Role, User
from app.storage import get_storage

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("peblo.bootstrap")


def main() -> int:
    session = SessionLocal()
    try:
        admin = session.query(User).filter(User.role == Role.admin).first()
        run = publish(session, get_storage(), admin.id if admin else None)
        session.commit()
        logger.info("Bootstrap publish: %s %s", run.status, run.counts or "")
    except PublishBlocked as blocked:
        session.commit()
        logger.warning(
            "Bootstrap publish blocked by %s validation problems. "
            "The API will still start; fix them in the CMS and publish there.",
            blocked.report["blocking_count"],
        )
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.warning("Bootstrap publish skipped: %s", exc)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
