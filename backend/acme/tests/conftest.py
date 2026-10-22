"""
Shared fixtures for the Acme backend tests.

Three layers:
  * unit         -> call router functions directly with a mocked AsyncSession
  * error        -> hit the FastAPI app over HTTP, DB + auth mocked out
  * integration  -> hit the FastAPI app over HTTP against a real Postgres DB

Assumptions about the app (adjust here if yours differ):
  * app.main exposes `app` (the FastAPI instance)
  * app.dependencies.require_role(...) depends on get_current_user
  * app.models exposes Base (the declarative base)
"""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.dependencies import get_current_user, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role  # noqa: E402


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def make_user(**overrides):
    """A lightweight stand-in for a User row."""
    data = dict(
        id=1,
        email="alice@acme.inc",
        hashed_password="hashed",
        first_name="Alice",
        last_name="Smith",
        role=Role.EMPLOYEE,
        is_active=True,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def result_returning(value):
    """Mimic the object returned by `await db.execute(...)`."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalars.return_value.all.return_value = value if isinstance(value, list) else [value]
    return result


# --------------------------------------------------------------------------- #
# Mocked DB session (unit + error tests)
# --------------------------------------------------------------------------- #
@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock(return_value=result_returning(None))
    db.get = AsyncMock(return_value=None)
    db.scalar = AsyncMock(return_value=None)
    db.commit = AsyncMock()
    db.delete = AsyncMock()
    db.add = MagicMock()

    async def _refresh(obj):
        # Fill in DB-generated fields so response models validate.
        if getattr(obj, "id", None) is None:
            obj.id = 99
        if getattr(obj, "is_active", None) is None:
            obj.is_active = True

    db.refresh = AsyncMock(side_effect=_refresh)
    return db


@pytest.fixture
def admin_user():
    return make_user(id=1, email="admin@acme.inc", role=Role.FACILITY_ADMIN)


@pytest.fixture
def employee_user():
    return make_user(id=2, email="bob@acme.inc", role=Role.EMPLOYEE)


@pytest_asyncio.fixture
async def mocked_client(mock_db):
    """HTTP client with get_db mocked. Use `as_user(...)` to set the caller."""

    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _get_db

    def as_user(user):
        if user is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = lambda: user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.as_user = as_user
        client.db = mock_db
        yield client

    app.dependency_overrides.clear()
