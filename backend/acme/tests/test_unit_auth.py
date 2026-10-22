"""
1. UNIT TESTS
Each router function is called directly, in isolation, with a mocked
AsyncSession. No HTTP layer, no database, no JWT verification.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.models import Engineer, Role, User
from app.routers import users as auth_router
from app.schemas.users import UserBase, UserCreate
from tests.conftest import make_user, result_returning

#pytestmark = pytest.mark.asyncio


def _create_payload(**overrides):
    data = dict(
        email="new.person@acme.inc",
        password="Str0ng!Passw0rd",
        first_name="New",
        last_name="Person",
        role=Role.EMPLOYEE,
    )
    data.update(overrides)
    return UserCreate(**data)


def _update_payload(**overrides):
    data = dict(
        email="alice@acme.inc",
        first_name="Alice",
        last_name="Smith",
        is_active=True,
        role=Role.EMPLOYEE,
    )
    data.update(overrides)
    return UserBase(**data)


def _route(path, method):
    """Fetch the endpoint function for a path, since two handlers share a name."""
    for r in auth_router.router.routes:
        if r.path == path and method in r.methods:
            return r.endpoint
    raise LookupError(f"{method} {path} not found")


register_admin = _route("/auth/register", "POST")
register_employee = _route("/auth/registerEmployee", "POST")


# --------------------------------------------------------------------------- #
# login
# --------------------------------------------------------------------------- #
class TestLogin:
    async def test_returns_bearer_token_for_valid_credentials(self, mock_db):
        user = make_user(role=Role.EMPLOYEE)
        mock_db.execute.return_value = result_returning(user)
        form = SimpleNamespace(username=user.email, password="secret")

        with patch.object(auth_router, "verify_password", return_value=True), \
             patch.object(auth_router, "create_access_token", return_value="tok") as create:
            token = await auth_router.login(form_data=form, db=mock_db)

        assert token.access_token == "tok"
        assert token.token_type == "bearer"
        create.assert_called_once_with(data={"sub": user.email, "role": Role.EMPLOYEE.value})

    async def test_unknown_email_raises_401(self, mock_db):
        mock_db.execute.return_value = result_returning(None)
        form = SimpleNamespace(username="ghost@acme.inc", password="x")

        with pytest.raises(HTTPException) as exc:
            await auth_router.login(form_data=form, db=mock_db)

        assert exc.value.status_code == 401
        assert exc.value.headers == {"WWW-Authenticate": "Bearer"}

    async def test_wrong_password_raises_401(self, mock_db):
        mock_db.execute.return_value = result_returning(make_user())
        form = SimpleNamespace(username="alice@acme.inc", password="wrong")

        with patch.object(auth_router, "verify_password", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await auth_router.login(form_data=form, db=mock_db)

        assert exc.value.status_code == 401
        assert exc.value.detail == "Incorrect email or password"


# --------------------------------------------------------------------------- #
# register (admin only) and registerEmployee (public)
# --------------------------------------------------------------------------- #
class TestRegisterAdmin:
    async def test_creates_user_with_hashed_password(self, mock_db, admin_user):
        payload = _create_payload()

        with patch.object(auth_router, "hash_password", return_value="HASHED"):
            user = await register_admin(payload=payload, db=mock_db, _=admin_user)

        added = mock_db.add.call_args.args[0]
        assert isinstance(added, User)
        assert added.hashed_password == "HASHED"
        assert added.email == payload.email
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(added)
        assert user is added

    async def test_duplicate_email_raises_400(self, mock_db, admin_user):
        mock_db.execute.return_value = result_returning(make_user())

        with pytest.raises(HTTPException) as exc:
            await register_admin(payload=_create_payload(), db=mock_db, _=admin_user)

        assert exc.value.status_code == 400
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()


class TestRegisterEmployee:
    async def test_creates_user_for_acme_email(self, mock_db):
        with patch.object(auth_router, "hash_password", return_value="HASHED"):
            user = await register_employee(payload=_create_payload(), db=mock_db)

        assert user.email == "new.person@acme.inc"
        mock_db.commit.assert_awaited_once()

    async def test_non_acme_email_raises_400_before_touching_db(self, mock_db):
        payload = _create_payload(email="someone@gmail.com")

        with pytest.raises(HTTPException) as exc:
            await register_employee(payload=payload, db=mock_db)

        assert exc.value.status_code == 400
        assert "acme.inc" in exc.value.detail
        mock_db.execute.assert_not_awaited()

    async def test_duplicate_email_raises_400(self, mock_db):
        mock_db.execute.return_value = result_returning(make_user())

        with pytest.raises(HTTPException) as exc:
            await register_employee(payload=_create_payload(), db=mock_db)

        assert exc.value.status_code == 400
        mock_db.add.assert_not_called()


# --------------------------------------------------------------------------- #
# list / get / delete
# --------------------------------------------------------------------------- #
class TestReadAndDelete:
    async def test_list_returns_all_users(self, mock_db, admin_user):
        users = [make_user(id=1), make_user(id=2, email="b@acme.inc")]
        mock_db.execute.return_value = result_returning(users)

        result = await auth_router.list_user(db=mock_db, _=admin_user)

        assert [u.id for u in result] == [1, 2]

    async def test_get_returns_user(self, mock_db, admin_user):
        mock_db.get.return_value = make_user(id=5)

        user = await auth_router.get_user(user_id=5, db=mock_db, _=admin_user)

        assert user.id == 5
        mock_db.get.assert_awaited_once_with(User, 5)

    async def test_get_missing_user_raises_404(self, mock_db, admin_user):
        with pytest.raises(HTTPException) as exc:
            await auth_router.get_user(user_id=404, db=mock_db, _=admin_user)
        assert exc.value.status_code == 404

    async def test_delete_removes_and_commits(self, mock_db, admin_user):
        target = make_user(id=7)
        mock_db.get.return_value = target

        result = await auth_router.delete_user(user_id=7, db=mock_db, _=admin_user)

        assert result is None
        mock_db.delete.assert_awaited_once_with(target)
        mock_db.commit.assert_awaited_once()

    async def test_delete_missing_user_raises_404(self, mock_db, admin_user):
        with pytest.raises(HTTPException) as exc:
            await auth_router.delete_user(user_id=7, db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        mock_db.delete.assert_not_awaited()


# --------------------------------------------------------------------------- #
# update
# --------------------------------------------------------------------------- #
class TestUpdate:
    async def test_updates_fields(self, mock_db, admin_user):
        target = make_user(id=3, first_name="Old")
        mock_db.get.return_value = target

        payload = _update_payload(first_name="New", is_active=False)
        user = await auth_router.update_user(user_id=3, payload=payload, db=mock_db, _=admin_user)

        assert user.first_name == "New"
        assert user.is_active is False
        mock_db.commit.assert_awaited_once()

    async def test_missing_user_raises_404(self, mock_db, admin_user):
        with pytest.raises(HTTPException) as exc:
            await auth_router.update_user(user_id=3, payload=_update_payload(), db=mock_db, _=admin_user)
        assert exc.value.status_code == 404

    async def test_cannot_promote_to_admin(self, mock_db, admin_user):
        mock_db.get.return_value = make_user(id=3, role=Role.EMPLOYEE)

        with pytest.raises(HTTPException) as exc:
            await auth_router.update_user(
                user_id=3, payload=_update_payload(role=Role.FACILITY_ADMIN), db=mock_db, _=admin_user
            )

        assert exc.value.status_code == 403
        mock_db.commit.assert_not_awaited()

    async def test_email_taken_by_other_user_raises_409(self, mock_db, admin_user):
        mock_db.get.return_value = make_user(id=3)
        mock_db.scalar.return_value = make_user(id=4)  # someone else owns the email

        with pytest.raises(HTTPException) as exc:
            await auth_router.update_user(user_id=3, payload=_update_payload(), db=mock_db, _=admin_user)

        assert exc.value.status_code == 409

    async def test_promoting_to_engineer_creates_engineer_record(self, mock_db, admin_user):
        mock_db.get.return_value = make_user(id=3, role=Role.EMPLOYEE)
        mock_db.scalar.side_effect = [None, None]  # email free, no engineer row yet

        await auth_router.update_user(
            user_id=3, payload=_update_payload(role=Role.ENGINEER), db=mock_db, _=admin_user
        )

        added = mock_db.add.call_args.args[0]
        assert isinstance(added, Engineer)
        assert added.user_id == 3
        assert added.is_available is True

    async def test_promoting_existing_engineer_record_is_not_duplicated(self, mock_db, admin_user):
        mock_db.get.return_value = make_user(id=3, role=Role.EMPLOYEE)
        mock_db.scalar.side_effect = [None, SimpleNamespace(user_id=3)]

        await auth_router.update_user(
            user_id=3, payload=_update_payload(role=Role.ENGINEER), db=mock_db, _=admin_user
        )

        mock_db.add.assert_not_called()

