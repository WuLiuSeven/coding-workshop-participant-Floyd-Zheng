"""
3. ERROR-HANDLING TESTS: engineer router
Every engineer route is admin-only. Auth, validation and not-found paths over HTTP,
with DB + current user mocked.
"""
import pytest

from app.models import Role
from tests.conftest import make_user

ADMIN = make_user(id=1, email="admin@acme.inc", role=Role.FACILITY_ADMIN)
ENGINEER = make_user(id=5, email="eng@acme.inc", role=Role.ENGINEER)
EMPLOYEE = make_user(id=2, email="bob@acme.inc", role=Role.EMPLOYEE)

VALID = {"user_id": 5, "is_available": True, "at_incident": None, "team": "Equipment"}

ALL_ROUTES = [
    ("get", "/engineer"), ("get", "/engineer/1"), ("post", "/engineer"),
    ("patch", "/engineer/1"), ("delete", "/engineer/1"),
]


def _kwargs(method):
    return {"json": VALID} if method in ("post", "patch") else {}


# --------------------------------------------------------------------------- #
# Authentication / authorisation
# --------------------------------------------------------------------------- #
class TestAuth:
    @pytest.mark.parametrize("method,path", ALL_ROUTES)
    async def test_every_route_rejects_anonymous(self, mocked_client, method, path):
        r = await getattr(mocked_client, method)(path, **_kwargs(method))
        assert r.status_code == 401

    @pytest.mark.parametrize("user", [EMPLOYEE, ENGINEER])
    @pytest.mark.parametrize("method,path", ALL_ROUTES)
    async def test_every_route_is_admin_only(self, mocked_client, user, method, path):
        # includes GET: engineers can't list or look up engineer records either
        mocked_client.as_user(user)
        r = await getattr(mocked_client, method)(path, **_kwargs(method))
        assert r.status_code == 403
        mocked_client.db.add.assert_not_called()
        mocked_client.db.commit.assert_not_awaited()
        mocked_client.db.delete.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Request validation (422)
# --------------------------------------------------------------------------- #
class TestValidation:
    @pytest.mark.parametrize("missing", ["user_id", "team"])
    async def test_create_missing_required_field(self, mocked_client, missing):
        mocked_client.as_user(ADMIN)
        body = {k: v for k, v in VALID.items() if k != missing}
        r = await mocked_client.post("/engineer", json=body)
        assert r.status_code == 422
        mocked_client.db.add.assert_not_called()

    @pytest.mark.parametrize("field,bad", [
        ("team", "Plumbing & Pizza"),   # not a Team value
        ("team", None),
        ("user_id", "abc"),
        ("user_id", None),
        ("is_available", "maybe"),
        ("at_incident", "ten"),
    ])
    async def test_create_bad_values(self, mocked_client, field, bad):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.post("/engineer", json={**VALID, field: bad})
        assert r.status_code == 422
        mocked_client.db.add.assert_not_called()

    async def test_create_empty_body(self, mocked_client):
        mocked_client.as_user(ADMIN)
        assert (await mocked_client.post("/engineer", json={})).status_code == 422

    @pytest.mark.parametrize("missing", ["user_id", "team"])
    async def test_update_is_a_full_replace(self, mocked_client, missing):
        # PATCH takes EngineerBase, so required fields must all be sent
        mocked_client.as_user(ADMIN)
        body = {k: v for k, v in VALID.items() if k != missing}
        r = await mocked_client.patch("/engineer/1", json=body)
        assert r.status_code == 422
        mocked_client.db.commit.assert_not_awaited()

    @pytest.mark.parametrize("bad_id", ["abc", "1.5"])
    async def test_non_integer_engineer_id(self, mocked_client, bad_id):
        mocked_client.as_user(ADMIN)
        assert (await mocked_client.get(f"/engineer/{bad_id}")).status_code == 422
        assert (await mocked_client.patch(f"/engineer/{bad_id}", json=VALID)).status_code == 422
        assert (await mocked_client.delete(f"/engineer/{bad_id}")).status_code == 422


# --------------------------------------------------------------------------- #
# Not found (404)
# --------------------------------------------------------------------------- #
class TestNotFound:
    async def test_get_missing(self, mocked_client):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.get("/engineer/123")
        assert r.status_code == 404
        assert r.json()["detail"] == "Engineer 123 not found"

    async def test_update_missing(self, mocked_client):
        # Currently a 500: the router uses status.HTTP_404_NOT_Found, which doesn't exist
        mocked_client.as_user(ADMIN)
        r = await mocked_client.patch("/engineer/123", json=VALID)
        assert r.status_code == 404
        assert "123" in r.json()["detail"]

    async def test_delete_missing(self, mocked_client):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.delete("/engineer/123")
        assert r.status_code == 404
        mocked_client.db.delete.assert_not_awaited()
