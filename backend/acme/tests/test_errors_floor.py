"""
3. ERROR-HANDLING TESTS: floor router
Auth, validation and not-found paths over HTTP, with DB + current user mocked.
"""
import pytest

from app.models import Role
from tests.conftest import make_user

ADMIN = make_user(id=1, email="admin@acme.inc", role=Role.FACILITY_ADMIN)
ENGINEER = make_user(id=5, email="eng@acme.inc", role=Role.ENGINEER)
EMPLOYEE = make_user(id=2, email="bob@acme.inc", role=Role.EMPLOYEE)

VALID = {"floor_number": 3, "building_id": 1}


# --------------------------------------------------------------------------- #
# Authentication / authorisation
# --------------------------------------------------------------------------- #
class TestAuth:
    @pytest.mark.parametrize("method,path", [
        ("get", "/floor"), ("get", "/floor/1"), ("post", "/floor"), ("patch", "/floor/1"), ("delete", "/floor/1"),
    ])
    async def test_every_route_rejects_anonymous(self, mocked_client, method, path):
        kwargs = {"json": VALID} if method in ("post", "patch") else {}
        r = await getattr(mocked_client, method)(path, **kwargs)
        assert r.status_code == 401

    @pytest.mark.parametrize("user", [EMPLOYEE, ENGINEER])
    @pytest.mark.parametrize("method,path", [("post", "/floor"), ("patch", "/floor/1"), ("delete", "/floor/1")])
    async def test_only_admin_can_write(self, mocked_client, user, method, path):
        mocked_client.as_user(user)
        kwargs = {"json": VALID} if method in ("post", "patch") else {}
        r = await getattr(mocked_client, method)(path, **kwargs)
        assert r.status_code == 403
        mocked_client.db.add.assert_not_called()
        mocked_client.db.commit.assert_not_awaited()
        mocked_client.db.delete.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Request validation (422)
# --------------------------------------------------------------------------- #
class TestValidation:
    @pytest.mark.parametrize("missing", ["floor_number", "building_id"])
    async def test_create_missing_field(self, mocked_client, missing):
        mocked_client.as_user(ADMIN)
        body = {k: v for k, v in VALID.items() if k != missing}
        r = await mocked_client.post("/floor", json=body)
        assert r.status_code == 422
        mocked_client.db.add.assert_not_called()

    @pytest.mark.parametrize("field,bad", [
        ("floor_number", "third"), ("floor_number", 2.5), ("building_id", "abc"), ("building_id", None),
    ])
    async def test_create_bad_values(self, mocked_client, field, bad):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.post("/floor", json={**VALID, field: bad})
        assert r.status_code == 422

    async def test_create_empty_body(self, mocked_client):
        mocked_client.as_user(ADMIN)
        assert (await mocked_client.post("/floor", json={})).status_code == 422

    @pytest.mark.parametrize("missing", ["floor_number", "building_id"])
    async def test_update_requires_both_fields(self, mocked_client, missing):
        # PATCH takes FloorBase, so it's really a full replace: both fields are required
        mocked_client.as_user(ADMIN)
        body = {k: v for k, v in VALID.items() if k != missing}
        r = await mocked_client.patch("/floor/1", json=body)
        assert r.status_code == 422
        mocked_client.db.commit.assert_not_awaited()

    @pytest.mark.parametrize("bad_id", ["abc", "1.5"])
    async def test_non_integer_floor_id(self, mocked_client, bad_id):
        mocked_client.as_user(ADMIN)
        assert (await mocked_client.get(f"/floor/{bad_id}")).status_code == 422
        assert (await mocked_client.patch(f"/floor/{bad_id}", json=VALID)).status_code == 422
        assert (await mocked_client.delete(f"/floor/{bad_id}")).status_code == 422


# --------------------------------------------------------------------------- #
# Not found (404)
# --------------------------------------------------------------------------- #
class TestNotFound:
    async def test_get_missing(self, mocked_client):
        mocked_client.as_user(EMPLOYEE)
        r = await mocked_client.get("/floor/123")
        assert r.status_code == 404
        assert r.json()["detail"] == "Floor 123 not found"

    async def test_delete_missing(self, mocked_client):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.delete("/floor/123")
        assert r.status_code == 404
        mocked_client.db.delete.assert_not_awaited()
