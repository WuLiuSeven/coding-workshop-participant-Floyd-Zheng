"""
3. ERROR-HANDLING TESTS: incident router
Validation, auth and not-found paths over HTTP, with DB + current user mocked.
"""
import pytest

from app.models import Role
from tests.conftest import make_user

ADMIN = make_user(id=1, email="admin@acme.inc", role=Role.FACILITY_ADMIN)
ENGINEER = make_user(id=5, email="eng@acme.inc", role=Role.ENGINEER)
EMPLOYEE = make_user(id=2, email="bob@acme.inc", role=Role.EMPLOYEE)

VALID_CREATE = {
    "seat_id": 1, "status": "Open", "priority": "High", "category": "Hardware",
    "is_escalated": False, "incident_notes": "Monitor flickers",
}


# --------------------------------------------------------------------------- #
# Authentication / authorisation
# --------------------------------------------------------------------------- #
class TestAuth:
    @pytest.mark.parametrize("method,path", [
        ("get", "/incident"), ("get", "/incident/mine"), ("get", "/incident/1"),
        ("post", "/incident"), ("patch", "/incident/1"), ("patch", "/incident/1/escalate"),
        ("delete", "/incident/1"),
    ])
    async def test_every_route_rejects_anonymous(self, mocked_client, method, path):
        kwargs = {"json": VALID_CREATE if method == "post" else {"status": "Open"}} if method in ("post", "patch") else {}
        r = await getattr(mocked_client, method)(path, **kwargs)
        assert r.status_code == 401

    async def test_employee_cannot_update(self, mocked_client):
        mocked_client.as_user(EMPLOYEE)
        r = await mocked_client.patch("/incident/1", json={"status": "In_Progress"})
        assert r.status_code == 403
        mocked_client.db.commit.assert_not_awaited()

    @pytest.mark.parametrize("user", [EMPLOYEE, ENGINEER])
    async def test_only_admin_can_delete(self, mocked_client, user):
        mocked_client.as_user(user)
        r = await mocked_client.delete("/incident/1")
        assert r.status_code == 403
        mocked_client.db.delete.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Request validation (422)
# --------------------------------------------------------------------------- #
class TestValidation:
    @pytest.mark.parametrize("missing", ["seat_id", "priority", "category"])
    async def test_create_missing_required_field(self, mocked_client, missing):
        mocked_client.as_user(EMPLOYEE)
        body = {k: v for k, v in VALID_CREATE.items() if k != missing}
        r = await mocked_client.post("/incident", json=body)
        assert r.status_code == 422
        mocked_client.db.add.assert_not_called()

    @pytest.mark.parametrize("field,bad", [
        ("priority", "Urgent!!"), ("category", "Coffee"), ("status", "Done"), ("seat_id", "abc"),
    ])
    async def test_create_rejects_invalid_values(self, mocked_client, field, bad):
        mocked_client.as_user(EMPLOYEE)
        r = await mocked_client.post("/incident", json={**VALID_CREATE, field: bad})
        assert r.status_code == 422

    async def test_create_notes_over_120_chars(self, mocked_client):
        mocked_client.as_user(EMPLOYEE)
        r = await mocked_client.post("/incident", json={**VALID_CREATE, "incident_notes": "x" * 121})
        # incident_notes is String(120); without schema validation Postgres rejects it as a 500
        assert r.status_code == 422
        mocked_client.db.add.assert_not_called()

    @pytest.mark.parametrize("bad_id", ["abc", "1.5"])
    async def test_non_integer_ids(self, mocked_client, bad_id):
        mocked_client.as_user(ADMIN)
        assert (await mocked_client.get(f"/incident/{bad_id}")).status_code == 422
        assert (await mocked_client.patch(f"/incident/{bad_id}", json={})).status_code == 422
        assert (await mocked_client.patch(f"/incident/{bad_id}/escalate")).status_code == 422
        assert (await mocked_client.delete(f"/incident/{bad_id}")).status_code == 422

    @pytest.mark.parametrize("field", ["status", "priority", "category", "is_escalated"])
    async def test_update_null_required_field(self, mocked_client, field):
        mocked_client.as_user(ENGINEER)
        mocked_client.db.get.return_value = make_user(id=1)  # any object stands in for the incident
        r = await mocked_client.patch("/incident/1", json={field: None})
        assert r.status_code == 422
        mocked_client.db.commit.assert_not_awaited()

    async def test_update_invalid_status_value(self, mocked_client):
        mocked_client.as_user(ENGINEER)
        r = await mocked_client.patch("/incident/1", json={"status": "Finished"})
        assert r.status_code == 422

    async def test_update_invalid_timestamp(self, mocked_client):
        mocked_client.as_user(ENGINEER)
        r = await mocked_client.patch("/incident/1", json={"resolved_at": "yesterday-ish"})
        assert r.status_code == 422


# --------------------------------------------------------------------------- #
# Not found (404)
# --------------------------------------------------------------------------- #
class TestNotFound:
    async def test_get(self, mocked_client):
        mocked_client.as_user(EMPLOYEE)
        r = await mocked_client.get("/incident/12345")
        assert r.status_code == 404
        assert r.json()["detail"] == "Incident 12345 not found"

    async def test_escalate(self, mocked_client):
        mocked_client.as_user(EMPLOYEE)
        assert (await mocked_client.patch("/incident/12345/escalate")).status_code == 404
        mocked_client.db.commit.assert_not_awaited()

    async def test_update(self, mocked_client):
        mocked_client.as_user(ENGINEER)
        assert (await mocked_client.patch("/incident/12345", json={"status": "Open"})).status_code == 404

    async def test_delete(self, mocked_client):
        mocked_client.as_user(ADMIN)
        assert (await mocked_client.delete("/incident/12345")).status_code == 404
        mocked_client.db.delete.assert_not_awaited()
