"""
2. INTEGRATION TESTS
Real HTTP requests through the FastAPI app, real JWTs, real Postgres.

Point TEST_DATABASE_URL at a THROWAWAY database. Every table is dropped and
recreated, so never use your deployed/RDS database:

    export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/acme_test"
    pytest -m integration

Skipped automatically when TEST_DATABASE_URL is not set.
"""
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set"),
]

from app.dependencies import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Role, User  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402

PASSWORD = "Str0ng!Passw0rd"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    async def _get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _seed_user(session_factory, email, role, password=PASSWORD):
    async with session_factory() as s:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            first_name=email.split("@")[0].title(),
            last_name="Test",
            role=role,
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user.id


def _auth(email, role):
    token = create_access_token(data={"sub": email, "role": role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(session_factory):
    await _seed_user(session_factory, "admin@acme.inc", Role.FACILITY_ADMIN)
    return _auth("admin@acme.inc", Role.FACILITY_ADMIN)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
async def test_login_round_trip(client, session_factory):
    await _seed_user(session_factory, "carol@acme.inc", Role.EMPLOYEE)

    r = await client.post("/auth/token", data={"username": "carol@acme.inc", "password": PASSWORD})

    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_wrong_password(client, session_factory):
    await _seed_user(session_factory, "carol@acme.inc", Role.EMPLOYEE)
    r = await client.post("/auth/token", data={"username": "carol@acme.inc", "password": "nope"})
    assert r.status_code == 401


async def test_employee_self_registration_persists_and_can_log_in(client, session_factory):
    payload = {
        "email": "dave@acme.inc",
        "password": PASSWORD,
        "first_name": "Dave",
        "last_name": "Test",
        "role": Role.EMPLOYEE.value,
    }
    r = await client.post("/auth/registerEmployee", json=payload)
    assert r.status_code == 201
    assert "password" not in r.json() and "hashed_password" not in r.json()

    async with session_factory() as s:
        stored = await s.scalar(select(User).where(User.email == "dave@acme.inc"))
    assert stored is not None
    assert stored.hashed_password != PASSWORD  # stored hashed, not plain

    login = await client.post("/auth/token", data={"username": "dave@acme.inc", "password": PASSWORD})
    assert login.status_code == 200


async def test_duplicate_registration_is_case_insensitive(client, session_factory):
    await _seed_user(session_factory, "erin@acme.inc", Role.EMPLOYEE)
    r = await client.post(
        "/auth/registerEmployee",
        json={"email": "ERIN@ACME.INC", "password": PASSWORD, "first_name": "E", "last_name": "T",
              "role": Role.EMPLOYEE.value},
    )
    assert r.status_code == 400


async def test_admin_crud_lifecycle(client, admin_headers):
    # create
    r = await client.post(
        "/auth/register",
        headers=admin_headers,
        json={"email": "frank@acme.inc", "password": PASSWORD, "first_name": "Frank", "last_name": "T",
              "role": Role.EMPLOYEE.value},
    )
    assert r.status_code == 201
    user_id = r.json()["id"]

    # list
    r = await client.get("/auth", headers=admin_headers)
    assert r.status_code == 200
    assert {u["email"] for u in r.json()} == {"admin@acme.inc", "frank@acme.inc"}

    # read
    r = await client.get(f"/auth/{user_id}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["first_name"] == "Frank"

    # update
    r = await client.patch(
        f"/auth/{user_id}",
        headers=admin_headers,
        json={"email": "frank@acme.inc", "first_name": "Franklin", "last_name": "T", "is_active": False,
              "role": Role.EMPLOYEE.value},
    )
    assert r.status_code == 200
    assert r.json()["first_name"] == "Franklin"
    assert r.json()["is_active"] is False

    # delete
    r = await client.delete(f"/auth/{user_id}", headers=admin_headers)
    assert r.status_code == 204

    r = await client.get(f"/auth/{user_id}", headers=admin_headers)
    assert r.status_code == 404


async def test_employee_token_cannot_list_users(client, session_factory):
    await _seed_user(session_factory, "gina@acme.inc", Role.EMPLOYEE)
    r = await client.get("/auth", headers=_auth("gina@acme.inc", Role.EMPLOYEE))
    assert r.status_code == 403


async def test_update_email_conflict_against_real_rows(client, session_factory, admin_headers):
    await _seed_user(session_factory, "hank@acme.inc", Role.EMPLOYEE)
    ivy_id = await _seed_user(session_factory, "ivy@acme.inc", Role.EMPLOYEE)

    r = await client.patch(
        f"/auth/{ivy_id}",
        headers=admin_headers,
        json={"email": "hank@acme.inc", "first_name": "Ivy", "last_name": "T", "is_active": True,
              "role": Role.EMPLOYEE.value},
    )
    assert r.status_code == 409
