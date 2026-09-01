import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="session")
def engine():
    from app.config import settings
    from app.models import Base

    admin_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS peblo_test WITH (FORCE)"))
        conn.execute(text("CREATE DATABASE peblo_test"))
    admin.dispose()

    test_engine = create_engine(settings.test_database_url)
    Base.metadata.create_all(test_engine)
    with test_engine.begin() as conn:
        conn.execute(text("INSERT INTO catalog_pointer (id, current_run_id) VALUES (1, NULL)"))
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db(engine):
    """A session rolled back after each test.

    Tests never see each other's rows, so execution order cannot matter.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, expire_on_commit=False)()
    yield session
    session.close()
    # A test that provoked an IntegrityError has already lost the transaction.
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def api(db):
    """HTTP client wired to the rolled-back test session."""
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app

    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def users(db):
    """The two seeded accounts.

    Idempotent, because the seeder creates the same two emails and a test may
    legitimately request both fixtures.
    """
    from sqlalchemy import select

    from app.auth import hash_password
    from app.models import Role, User

    found = {}
    for key, email, role in [
        ("editor", "editor@peblo.test", Role.editor),
        ("admin", "admin@peblo.test", Role.admin),
    ]:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, password_hash=hash_password("pw"), role=role)
            db.add(user)
            db.flush()
        found[key] = user
    return found


@pytest.fixture
def editor_headers(users):
    from app.auth import create_token

    return {"Authorization": f"Bearer {create_token(users['editor'])}"}


@pytest.fixture
def admin_headers(users):
    from app.auth import create_token

    return {"Authorization": f"Bearer {create_token(users['admin'])}"}


@pytest.fixture
def storage(tmp_path):
    from app.storage import LocalDiskStorage

    return LocalDiskStorage(tmp_path, "http://t/media")
