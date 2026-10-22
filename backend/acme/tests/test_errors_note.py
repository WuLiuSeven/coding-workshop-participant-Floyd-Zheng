"""
3. ERROR-HANDLING TESTS: note router
Auth, validation and not-found paths over HTTP, with DB + current user mocked.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models import Incident, Note, Role
from tests.conftest import make_user

ADMIN = make_user(id=1, email="admin@acme.inc", role=Role.FACILITY_ADMIN)
ENGINEER = make_user(id=5, email="eng@acme.inc", role=Role.ENGINEER)
EMPLOYEE = make_user(id=2, email="bob@acme.inc", role=Role.EMPLOYEE)

VALID_CREATE = {"incident_at": 10, "comments": "Replaced the cable"}


def stock_db(db, incidents=(), notes=()):
    rows = {Incident: {i.id: i for i in incidents}, Note: {n.id: n for n in notes}}
    db.get = AsyncMock(side_effect=lambda model, pk: rows.get(model, {}).get(pk))


# --------------------------------------------------------------------------- #
# Authentication / authorisation
# --------------------------------------------------------------------------- #
class TestAuth:
    @pytest.mark.parametrize("method,path", [
        ("get", "/note"), ("get", "/note/1"), ("post", "/note"), ("patch", "/note/1"), ("delete", "/note/1"),
    ])
    async def test_every_route_rejects_anonymous(self, mocked_client, method, path):
        kwargs = {"json": VALID_CREATE} if method in ("post", "patch") else {}
        r = await getattr(mocked_client, method)(path, **kwargs)
        assert r.status_code == 401

    @pytest.mark.parametrize("user", [EMPLOYEE, ENGINEER])
    @pytest.mark.parametrize("method,path", [("patch", "/note/1"), ("delete", "/note/1")])
    async def test_only_admin_can_edit_or_delete(self, mocked_client, user, method, path):
        mocked_client.as_user(user)
        kwargs = {"json": {"comments": "changed"}} if method == "patch" else {}
        r = await getattr(mocked_client, method)(path, **kwargs)
        assert r.status_code == 403
        mocked_client.db.commit.assert_not_awaited()
        mocked_client.db.delete.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Request validation (422)
# --------------------------------------------------------------------------- #
class TestValidation:
    @pytest.mark.parametrize("missing", ["incident_at"])
    async def test_create_missing_field(self, mocked_client, missing):
        mocked_client.as_user(EMPLOYEE)
        body = {k: v for k, v in VALID_CREATE.items() if k != missing}
        r = await mocked_client.post("/note", json=body)
        assert r.status_code == 422
        mocked_client.db.add.assert_not_called()

    @pytest.mark.parametrize("bad", ["ten", 1.5, None])
    async def test_create_bad_incident_id(self, mocked_client, bad):
        mocked_client.as_user(EMPLOYEE)
        r = await mocked_client.post("/note", json={**VALID_CREATE, "incident_at": bad})
        assert r.status_code == 422

    async def test_create_empty_body(self, mocked_client):
        mocked_client.as_user(EMPLOYEE)
        assert (await mocked_client.post("/note", json={})).status_code == 422

    async def test_create_comment_over_250_chars(self, mocked_client):
        mocked_client.as_user(EMPLOYEE)
        r = await mocked_client.post("/note", json={**VALID_CREATE, "comments": "x" * 251})
        # comments is String(250); without schema validation Postgres rejects it as a 500
        assert r.status_code == 422
        mocked_client.db.add.assert_not_called()

    @pytest.mark.parametrize("bad_id", ["abc", "1.5"])
    async def test_non_integer_note_id(self, mocked_client, bad_id):
        mocked_client.as_user(ADMIN)
        assert (await mocked_client.get(f"/note/{bad_id}")).status_code == 422
        assert (await mocked_client.patch(f"/note/{bad_id}", json={})).status_code == 422
        assert (await mocked_client.delete(f"/note/{bad_id}")).status_code == 422

    async def test_update_null_incident(self, mocked_client):
        mocked_client.as_user(ADMIN)
        stock_db(mocked_client.db, notes=[SimpleNamespace(id=1, incident_at=10, comments="c")])
        r = await mocked_client.patch("/note/1", json={"incident_at": None})
        assert r.status_code == 422
        mocked_client.db.commit.assert_not_awaited()

    async def test_update_wrong_type(self, mocked_client):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.patch("/note/1", json={"incident_at": "eleven"})
        assert r.status_code == 422


# --------------------------------------------------------------------------- #
# Not found (404)
# --------------------------------------------------------------------------- #
class TestNotFound:
    async def test_get_missing(self, mocked_client):
        mocked_client.as_user(EMPLOYEE)
        stock_db(mocked_client.db)
        r = await mocked_client.get("/note/123")
        assert r.status_code == 404
        assert r.json()["detail"] == "Note 123 not found"

    async def test_create_on_unknown_incident(self, mocked_client):
        mocked_client.as_user(EMPLOYEE)
        stock_db(mocked_client.db)
        r = await mocked_client.post("/note", json=VALID_CREATE)
        assert r.status_code == 404
        assert r.json()["detail"] == "Incident 10 not found"
        mocked_client.db.add.assert_not_called()

    async def test_update_missing_note(self, mocked_client):
        mocked_client.as_user(ADMIN)
        stock_db(mocked_client.db)
        assert (await mocked_client.patch("/note/123", json={"comments": "x"})).status_code == 404

    async def test_update_to_unknown_incident(self, mocked_client):
        mocked_client.as_user(ADMIN)
        stock_db(mocked_client.db, notes=[SimpleNamespace(id=1, incident_at=10, comments="c")])
        r = await mocked_client.patch("/note/1", json={"incident_at": 404})
        assert r.status_code == 404
        assert r.json()["detail"] == "Incident 404 not found"

    async def test_delete_missing(self, mocked_client):
        mocked_client.as_user(ADMIN)
        stock_db(mocked_client.db)
        assert (await mocked_client.delete("/note/123")).status_code == 404
        mocked_client.db.delete.assert_not_awaited()
