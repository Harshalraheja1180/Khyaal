import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Permission, Role, RolePermission
from app.seed import ensure_access_catalog

TEST_URL = os.getenv("TEST_DATABASE_URL", settings.database_url)
test_engine = create_engine(TEST_URL, pool_pre_ping=True)
TestSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    with TestSession() as db:
        ensure_access_catalog(db)
        db.commit()
    yield
    Base.metadata.drop_all(test_engine)


@pytest.fixture(autouse=True)
def clean_tables(schema):
    with test_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    with TestSession() as db:
        ensure_access_catalog(db)
        db.commit()


@pytest.fixture
def db_session():
    with TestSession() as db:
        yield db


@pytest.fixture
def client():
    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def register_user(client):
    def create(email: str | None = None, role: str = "GUARDIAN", mode: str = "OLDER_ADULT"):
        email = email or f"{uuid.uuid4().hex}@example.com"
        result = client.post("/api/v1/auth/register", json={
            "email": email, "password": "StrongDemoPassword!234", "display_name": "Demo User",
            "role": role, "mode": mode,
        })
        assert result.status_code == 201, result.text
        return result.json()
    return create


@pytest.fixture
def auth_headers():
    def headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}
    return headers
