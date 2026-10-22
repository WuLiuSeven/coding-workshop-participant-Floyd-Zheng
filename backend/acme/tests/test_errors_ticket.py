"""
3. ERROR-HANDLING TESTS: ticket router
Auth, validation, not-found and conflict paths over HTTP, with DB + current user mocked.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models import Engineer, Incident, Role, Ticket
from tests.conftest import make_user

ADMIN = make_user(id=1, email="admin@acme.inc", role=Role.FACILITY_ADMIN)
ENGINEER = make_user(id=5, email="eng@acme.inc", role=Role.ENGINEER)
EMPLOYEE = make_user(id=2, email="bob@acme.inc", role=Role.EMPLOYEE)

VALID_CREATE = {"engineer_id": 3, "incident_id": 10}


def stock_db(db, engineers=(), incidents=(), tickets=()):
    rows = {
        Engineer: {e.id: e for e in engineers},
        Incident: {i.id: i for i in incidents},
        Ticket: {t.id: t for t in tickets},
    }
    db.get = AsyncMock(side_effect=lambda model, pk: rows.get(model, {}).get(pk))


# --------------------------------------------------------------------------- #
# Authentication / authorisation
# --------------------------------------------------------------------------- #
class TestAuth:
    @pytest.mark.parametrize("method,path", [
        ("get", "/ticket"), ("get", "/ticket/mine"), ("get", "/ticket/1"),
        ("post", "/ticket"), ("patch", "/ticket/1"), ("delete", "/ticket/1"),
    ])
    async def test_every_route_rejects_anonymous(self, mocked_client, method, path):
        kwargs = {"json": VALID_CREATE} if method in ("post", "patch") else {}
        r = await getattr(mocked_client, method)(path, **kwargs)
        assert r.status_code == 401

    @pytest.mark.parametrize("user", [EMPLOYEE, ENGINEER])
    @pytest.mark.parametrize("method,path", [("post", "/ticket"), ("patch", "/ticket/1"), ("delete", "/ticket/1")])
    async def test_only_admin_can_write(self, mocked_client, user, method, path):
        mocked_client.as_user(user)
        kwargs = {"json": VALID_CREATE} if method in ("post", "patch") else {}
        r = await getattr(mocked_client, method)(path, **kwargs)
        assert r.status_code == 403
        mocked_client.db.add.assert_not_called()
        mocked_client.db.commit.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Request validation (422)
# --------------------------------------------------------------------------- #
class TestValidation:
    @pytest.mark.parametrize("missing", ["engineer_id", "incident_id"])
    async def test_create_missing_field(self, mocked_client, missing):
        mocked_client.as_user(ADMIN)
        body = {k: v for k, v in VALID_CREATE.items() if k != missing}
        r = await mocked_client.post("/ticket", json=body)
        assert r.status_code == 422
        mocked_client.db.get.assert_not_awaited()

    @pytest.mark.parametrize("field,bad", [("engineer_id", "abc"), ("incident_id", "ten"), ("engineer_id", 1.5)])
    async def test_create_non_integer_ids(self, mocked_client, field, bad):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.post("/ticket", json={**VALID_CREATE, field: bad})
        assert r.status_code == 422

    async def test_create_empty_body(self, mocked_client):
        mocked_client.as_user(ADMIN)
        assert (await mocked_client.post("/ticket", json={})).status_code == 422

    @pytest.mark.parametrize("bad_id", ["abc", "1.5"])
    async def test_non_integer_ticket_id(self, mocked_client, bad_id):
        mocked_client.as_user(ADMIN)
        assert (await mocked_client.get(f"/ticket/{bad_id}")).status_code == 422
        assert (await mocked_client.patch(f"/ticket/{bad_id}", json={})).status_code == 422
        assert (await mocked_client.delete(f"/ticket/{bad_id}")).status_code == 422

    @pytest.mark.parametrize("field", ["engineer_id", "incident_id"])
    async def test_update_null_field(self, mocked_client, field):
        mocked_client.as_user(ADMIN)
        stock_db(mocked_client.db, tickets=[SimpleNamespace(id=1, engineer_id=3, incident_id=10)])
        r = await mocked_client.patch("/ticket/1", json={field: None})
        assert r.status_code == 422
        mocked_client.db.commit.assert_not_awaited()

    async def test_update_wrong_type(self, mocked_client):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.patch("/ticket/1", json={"engineer_id": "someone"})
        assert r.status_code == 422


# --------------------------------------------------------------------------- #
# Not found (404) and conflict (409)
# --------------------------------------------------------------------------- #
class TestNotFoundAndConflict:
    async def test_get_missing(self, mocked_client):
        mocked_client.as_user(EMPLOYEE)
        stock_db(mocked_client.db)
        r = await mocked_client.get("/ticket/123")
        assert r.status_code == 404
        assert r.json()["detail"] == "Ticket 123 not found"

    async def test_create_unknown_engineer(self, mocked_client):
        mocked_client.as_user(ADMIN)
        stock_db(mocked_client.db, incidents=[SimpleNamespace(id=10, resolved_at=None, acknowledged_at=None)])
        r = await mocked_client.post("/ticket", json=VALID_CREATE)
        assert r.status_code == 404
        assert r.json()["detail"] == "Engineer 3 not found"

    async def test_create_unknown_incident(self, mocked_client):
        mocked_client.as_user(ADMIN)
        stock_db(mocked_client.db, engineers=[SimpleNamespace(id=3, at_incident=None, is_available=True)])
        r = await mocked_client.post("/ticket", json=VALID_CREATE)
        assert r.status_code == 404
        assert r.json()["detail"] == "Incident 10 not found"

    async def test_create_on_resolved_incident_returns_409(self, mocked_client):
        mocked_client.as_user(ADMIN)
        eng = SimpleNamespace(id=3, at_incident=None, is_available=True)
        stock_db(
            mocked_client.db,
            engineers=[eng],
            incidents=[SimpleNamespace(id=10, resolved_at="2026-10-22T12:00:00Z", acknowledged_at=None)],
        )
        r = await mocked_client.post("/ticket", json=VALID_CREATE)
        assert r.status_code == 409
        assert "already completed" in r.json()["detail"]
        assert eng.is_available is True
        mocked_client.db.commit.assert_not_awaited()

    async def test_update_missing_ticket(self, mocked_client):
        mocked_client.as_user(ADMIN)
        stock_db(mocked_client.db)
        assert (await mocked_client.patch("/ticket/123", json={"engineer_id": 3})).status_code == 404

    async def test_update_to_unknown_engineer(self, mocked_client):
        mocked_client.as_user(ADMIN)
        stock_db(mocked_client.db, tickets=[SimpleNamespace(id=1, engineer_id=3, incident_id=10)])
        r = await mocked_client.patch("/ticket/1", json={"engineer_id": 404})
        assert r.status_code == 404
        assert r.json()["detail"] == "Engineer 404 not found"

    async def test_update_to_unknown_incident(self, mocked_client):
        mocked_client.as_user(ADMIN)
        stock_db(mocked_client.db, tickets=[SimpleNamespace(id=1, engineer_id=3, incident_id=10)])
        r = await mocked_client.patch("/ticket/1", json={"incident_id": 404})
        assert r.status_code == 404
        assert r.json()["detail"] == "Incident 404 not found"

    async def test_delete_missing(self, mocked_client):
        mocked_client.as_user(ADMIN)
        stock_db(mocked_client.db)
        assert (await mocked_client.delete("/ticket/123")).status_code == 404
        mocked_client.db.delete.assert_not_awaited()
