"""
1. UNIT TESTS: engineer router
Each route function is called directly with a mocked AsyncSession.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models import Engineer, Incident, User
from app.routers import engineer as engineer_router
from app.schemas.engineer import EngineerBase
from tests.conftest import result_returning

TEAM = "Equipment"   # must be a valid Team value


def engineer(**kw):
    data = dict(id=3, user_id=5, is_available=True, at_incident=None, team=TEAM)
    data.update(kw)
    return SimpleNamespace(**data)


def payload(**kw):
    data = dict(user_id=5, is_available=True, at_incident=None, team=TEAM)
    data.update(kw)
    return EngineerBase(**data)


def stock_db(mock_db, engineers=(), users=(SimpleNamespace(id=5),), incidents=(SimpleNamespace(id=10),)):
    """db.get(Model, id) returns the matching fake row, or None. User 5 and incident 10 exist by default."""
    rows = {
        Engineer: {e.id: e for e in engineers},
        User: {u.id: u for u in users},
        Incident: {i.id: i for i in incidents},
    }
    mock_db.get = AsyncMock(side_effect=lambda model, pk: rows.get(model, {}).get(pk))


def team_value(team):
    return getattr(team, "value", team)


# --------------------------------------------------------------------------- #
# list / get
# --------------------------------------------------------------------------- #
class TestRead:
    async def test_list_returns_all(self, mock_db, admin_user):
        mock_db.execute.return_value = result_returning([engineer(id=1), engineer(id=2, user_id=6)])
        result = await engineer_router.list_engineer(db=mock_db, _=admin_user)
        assert [e.id for e in result] == [1, 2]

    async def test_list_empty(self, mock_db, admin_user):
        mock_db.execute.return_value = result_returning([])
        assert await engineer_router.list_engineer(db=mock_db, _=admin_user) == []

    async def test_get_returns_engineer(self, mock_db, admin_user):
        stock_db(mock_db, engineers=[engineer(id=3)])
        result = await engineer_router.get_engineer(engineer_id=3, db=mock_db, _=admin_user)
        assert result.user_id == 5

    async def test_get_missing_raises_404(self, mock_db, admin_user):
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await engineer_router.get_engineer(engineer_id=99, db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Engineer 99 not found"


# --------------------------------------------------------------------------- #
# create
# --------------------------------------------------------------------------- #
class TestCreate:
    async def test_creates_available_engineer(self, mock_db, admin_user):
        stock_db(mock_db)

        result = await engineer_router.create_engineer(payload=payload(), db=mock_db, _=admin_user)

        added = mock_db.add.call_args.args[0]
        assert isinstance(added, Engineer)
        assert added.user_id == 5
        assert added.is_available is True
        assert added.at_incident is None
        assert team_value(added.team) == TEAM
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(added)
        assert result is added

    async def test_creates_engineer_already_on_an_incident(self, mock_db, admin_user):
        stock_db(mock_db)
        await engineer_router.create_engineer(
            payload=payload(is_available=False, at_incident=10), db=mock_db, _=admin_user,
        )
        added = mock_db.add.call_args.args[0]
        assert (added.is_available, added.at_incident) == (False, 10)

    @pytest.mark.xfail(reason="create_engineer doesn't check the user exists; the FK error surfaces as a 500")
    async def test_unknown_user_raises_404(self, mock_db, admin_user):
        stock_db(mock_db, users=())
        with pytest.raises(HTTPException) as exc:
            await engineer_router.create_engineer(payload=payload(user_id=404), db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        mock_db.add.assert_not_called()

    @pytest.mark.xfail(reason="create_engineer doesn't stop a second engineer record for the same user")
    async def test_duplicate_engineer_for_same_user_raises_409(self, mock_db, admin_user):
        stock_db(mock_db)
        mock_db.scalar.return_value = engineer(id=3, user_id=5)    # an engineer row already exists
        mock_db.execute.return_value = result_returning(engineer(id=3, user_id=5))
        with pytest.raises(HTTPException) as exc:
            await engineer_router.create_engineer(payload=payload(user_id=5), db=mock_db, _=admin_user)
        assert exc.value.status_code == 409
        mock_db.add.assert_not_called()


# --------------------------------------------------------------------------- #
# update
# --------------------------------------------------------------------------- #
class TestUpdate:
    async def test_replaces_all_fields(self, mock_db, admin_user):
        e = engineer(is_available=True, at_incident=None, user_id=5)
        stock_db(mock_db, engineers=[e], users=[SimpleNamespace(id=5), SimpleNamespace(id=6)])

        result = await engineer_router.update_engineer(
            engineer_id=3, payload=payload(user_id=6, is_available=False, at_incident=10),
            db=mock_db, _=admin_user,
        )

        assert (result.user_id, result.is_available, result.at_incident) == (6, False, 10)
        assert team_value(result.team) == TEAM
        mock_db.commit.assert_awaited_once()

    async def test_freeing_an_engineer(self, mock_db, admin_user):
        e = engineer(is_available=False, at_incident=10)
        stock_db(mock_db, engineers=[e])

        await engineer_router.update_engineer(
            engineer_id=3, payload=payload(is_available=True, at_incident=None), db=mock_db, _=admin_user,
        )

        assert (e.is_available, e.at_incident) == (True, None)

    async def test_missing_engineer_raises_404(self, mock_db, admin_user):
        # Currently crashes: the router uses status.HTTP_404_NOT_Found (lowercase "ound"),
        # which doesn't exist, so this raises AttributeError -> 500 instead of a 404.
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await engineer_router.update_engineer(engineer_id=99, payload=payload(), db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        assert "99" in exc.value.detail      # message should name the missing id, not "None"
        mock_db.commit.assert_not_awaited()

    @pytest.mark.xfail(reason="update_engineer doesn't check the new user exists")
    async def test_unknown_user_raises_404(self, mock_db, admin_user):
        e = engineer(user_id=5)
        stock_db(mock_db, engineers=[e], users=[SimpleNamespace(id=5)])
        with pytest.raises(HTTPException) as exc:
            await engineer_router.update_engineer(
                engineer_id=3, payload=payload(user_id=404), db=mock_db, _=admin_user,
            )
        assert exc.value.status_code == 404
        assert e.user_id == 5

    @pytest.mark.xfail(reason="update_engineer doesn't check at_incident points at a real incident")
    async def test_unknown_incident_raises_404(self, mock_db, admin_user):
        e = engineer()
        stock_db(mock_db, engineers=[e], incidents=())
        with pytest.raises(HTTPException) as exc:
            await engineer_router.update_engineer(
                engineer_id=3, payload=payload(is_available=False, at_incident=404), db=mock_db, _=admin_user,
            )
        assert exc.value.status_code == 404
        assert e.at_incident is None


# --------------------------------------------------------------------------- #
# delete
# --------------------------------------------------------------------------- #
class TestDelete:
    async def test_deletes_and_commits(self, mock_db, admin_user):
        e = engineer()
        stock_db(mock_db, engineers=[e])

        result = await engineer_router.delete_engineer(engineer_id=3, db=mock_db, _=admin_user)

        assert result is None
        mock_db.delete.assert_awaited_once_with(e)
        mock_db.commit.assert_awaited_once()

    async def test_missing_engineer_raises_404(self, mock_db, admin_user):
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await engineer_router.delete_engineer(engineer_id=99, db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        assert "99" in exc.value.detail
        mock_db.delete.assert_not_awaited()
