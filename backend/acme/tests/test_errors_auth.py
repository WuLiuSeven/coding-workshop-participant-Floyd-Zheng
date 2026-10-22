"""
3. ERROR-HANDLING TESTS
Validation and error paths for the /auth CRUD endpoints, exercised over HTTP
so FastAPI's request validation, status codes, and headers are covered.
DB and current-user are mocked (see conftest.mocked_client).

Tests marked `xfail` describe behaviour that is arguably a bug in the current
router. They pass (as expected failures) today; fix the code and they'll XPASS.
"""
import pytest

from app.models import Role
from tests.conftest import make_user, result_returning

pytestmark = pytest.mark.asyncio

ADMIN = make_user(id=1, email="admin@acme.inc", role=Role.FACILITY_ADMIN)
EMPLOYEE = make_user(id=2, email="bob@acme.inc", role=Role.EMPLOYEE)

VALID_CREATE = {
    "email": "new.person@acme.inc",
    "password": "Str0ng!Passw0rd",
    "first_name": "New",
    "last_name": "Person",
    "role": Role.EMPLOYEE.value,
}
VALID_UPDATE = {
    "email": "alice@acme.inc",
    "first_name": "Alice",
    "last_name": "Smith",
    "is_active": True,
    "role": Role.EMPLOYEE.value,
}


# --------------------------------------------------------------------------- #
# Request validation (422)
# --------------------------------------------------------------------------- #
class TestValidation:
    @pytest.mark.parametrize("missing", ["email", "password", "first_name", "last_name", "role"])
    async def test_register_employee_missing_field_returns_422(self, mocked_client, missing):
        body = {k: v for k, v in VALID_CREATE.items() if k != missing}
        r = await mocked_client.post("/auth/registerEmployee", json=body)
        assert r.status_code == 422

    async def test_register_employee_invalid_role_returns_422(self, mocked_client):
        r = await mocked_client.post("/auth/registerEmployee", json={**VALID_CREATE, "role": "SuperUser"})
        assert r.status_code == 422

    async def test_register_employee_empty_body_returns_422(self, mocked_client):
        r = await mocked_client.post("/auth/registerEmployee", json={})
        assert r.status_code == 422

    async def test_login_requires_form_fields(self, mocked_client):
        r = await mocked_client.post("/auth/token", data={})
        assert r.status_code == 422

    async def test_login_rejects_json_body(self, mocked_client):
        r = await mocked_client.post("/auth/token", json={"username": "a", "password": "b"})
        assert r.status_code == 422

    @pytest.mark.parametrize("bad_id", ["abc", "1.5"])
    async def test_non_integer_user_id_returns_422(self, mocked_client, bad_id):
        mocked_client.as_user(ADMIN)
        assert (await mocked_client.get(f"/auth/{bad_id}")).status_code == 422
        assert (await mocked_client.delete(f"/auth/{bad_id}")).status_code == 422

    async def test_update_with_invalid_is_active_returns_422(self, mocked_client):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.patch("/auth/1", json={**VALID_UPDATE, "is_active": "maybe"})
        assert r.status_code == 422


# --------------------------------------------------------------------------- #
# Authentication / authorisation (401 / 403)
# --------------------------------------------------------------------------- #
class TestAuthErrors:
    @pytest.mark.parametrize(
        "method,path",
        [("get", "/auth"), ("get", "/auth/1"), ("delete", "/auth/1"), ("patch", "/auth/1"), ("post", "/auth/register")],
    )
    async def test_admin_routes_reject_anonymous(self, mocked_client, method, path):
        kwargs = {"json": VALID_UPDATE if method == "patch" else VALID_CREATE} if method in ("patch", "post") else {}
        r = await getattr(mocked_client, method)(path, **kwargs)
        assert r.status_code == 401

    @pytest.mark.parametrize("method,path", [("get", "/auth"), ("get", "/auth/1"), ("delete", "/auth/1")])
    async def test_admin_routes_reject_employee(self, mocked_client, method, path):
        mocked_client.as_user(EMPLOYEE)
        r = await getattr(mocked_client, method)(path)
        assert r.status_code == 403

    async def test_garbage_bearer_token_returns_401(self, mocked_client):
        r = await mocked_client.get("/auth", headers={"Authorization": "Bearer not-a-jwt"})
        assert r.status_code == 401

    async def test_login_unknown_user_returns_401_with_header(self, mocked_client):
        mocked_client.db.execute.return_value = result_returning(None)
        r = await mocked_client.post("/auth/token", data={"username": "x@acme.inc", "password": "p"})
        assert r.status_code == 401
        assert r.headers.get("www-authenticate") == "Bearer"
        assert r.json()["detail"] == "Incorrect email or password"


# --------------------------------------------------------------------------- #
# Business-rule errors (400 / 404 / 409)
# --------------------------------------------------------------------------- #
class TestBusinessRules:
    async def test_register_employee_non_acme_email_returns_400(self, mocked_client):
        r = await mocked_client.post("/auth/registerEmployee", json={**VALID_CREATE, "email": "x@gmail.com"})
        assert r.status_code == 400
        mocked_client.db.add.assert_not_called()

    async def test_register_employee_duplicate_email_returns_400(self, mocked_client):
        mocked_client.db.execute.return_value = result_returning(make_user())
        r = await mocked_client.post("/auth/registerEmployee", json=VALID_CREATE)
        assert r.status_code == 400
        assert "already used" in r.json()["detail"]

    async def test_get_missing_user_returns_404(self, mocked_client):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.get("/auth/12345")
        assert r.status_code == 404

    async def test_delete_missing_user_returns_404(self, mocked_client):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.delete("/auth/12345")
        assert r.status_code == 404

    async def test_update_missing_user_returns_404(self, mocked_client):
        mocked_client.as_user(ADMIN)
        r = await mocked_client.patch("/auth/12345", json=VALID_UPDATE)
        assert r.status_code == 404

    async def test_update_promote_to_admin_returns_403(self, mocked_client):
        mocked_client.as_user(ADMIN)
        mocked_client.db.get.return_value = make_user(id=3)
        r = await mocked_client.patch("/auth/3", json={**VALID_UPDATE, "role": Role.FACILITY_ADMIN.value})
        assert r.status_code == 403

    async def test_update_email_conflict_returns_409(self, mocked_client):
        mocked_client.as_user(ADMIN)
        mocked_client.db.get.return_value = make_user(id=3)
        mocked_client.db.scalar.return_value = make_user(id=4)
        r = await mocked_client.patch("/auth/3", json=VALID_UPDATE)
        assert r.status_code == 409

