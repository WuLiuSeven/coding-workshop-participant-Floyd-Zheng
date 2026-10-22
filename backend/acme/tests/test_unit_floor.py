"""
1. UNIT TESTS: floor router
Each route function is called directly with a mocked AsyncSession.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models import Floor, Building
from app.routers import floor as floor_router
from app.schemas.floor import FloorBase
from tests.conftest import result_returning

def floor(**kw):
    data = dict(id=2, floor_number=3, building_id=1)
    data.update(kw)
    return SimpleNamespace(**data)


def stock_db(mock_db, floors=(), buildings=(SimpleNamespace(id=1),)):
    """db.get(Model, id) returns the matching fake row, or None. Building 1 exists by default."""
    rows = {Floor: {f.id: f for f in floors}, Building: {b.id: b for b in buildings}}
    mock_db.get = AsyncMock(side_effect=lambda model, pk: rows.get(model, {}).get(pk))

# --------------------------------------------------------------------------- #
# list / get
# --------------------------------------------------------------------------- #
class TestRead:
    async def test_list_returns_all(self, mock_db, employee_user):
        mock_db.execute.return_value = result_returning([floor(id=1), floor(id=2)])
        result = await floor_router.list_floor(db=mock_db, _=employee_user)
        assert [f.id for f in result] == [1, 2]

    async def test_list_empty(self, mock_db, employee_user):
        mock_db.execute.return_value = result_returning([])
        assert await floor_router.list_floor(db=mock_db, _=employee_user) == []

    async def test_get_returns_floor(self, mock_db, employee_user):
        stock_db(mock_db, floors=[floor(id=2)])
        result = await floor_router.get_floor(floor_id=2, db=mock_db, _=employee_user)
        assert result.floor_number == 3

    async def test_get_missing_raises_404(self, mock_db, employee_user):
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await floor_router.get_floor(floor_id=99, db=mock_db, _=employee_user)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Floor 99 not found"


# --------------------------------------------------------------------------- #
# create
# --------------------------------------------------------------------------- #
class TestCreate:
    async def test_creates_floor(self, mock_db, admin_user):
        stock_db(mock_db)
        result = await floor_router.create_floor(
            payload=FloorBase(floor_number=4, building_id=1), db=mock_db, _=admin_user,
        )

        added = mock_db.add.call_args.args[0]
        assert isinstance(added, Floor)
        assert (added.floor_number, added.building_id) == (4, 1)
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(added)
        assert result is added

    @pytest.mark.parametrize("number", [0, -1])
    async def test_ground_and_basement_floors_allowed(self, mock_db, admin_user, number):
        stock_db(mock_db)
        await floor_router.create_floor(
            payload=FloorBase(floor_number=number, building_id=1), db=mock_db, _=admin_user,
        )
        assert mock_db.add.call_args.args[0].floor_number == number

    async def test_unknown_building_raises_404(self, mock_db, admin_user):
        stock_db(mock_db, buildings=())
        with pytest.raises(HTTPException) as exc:
            await floor_router.create_floor(
                payload=FloorBase(floor_number=4, building_id=404), db=mock_db, _=admin_user,
            )
        assert exc.value.status_code == 404
        assert exc.value.detail == "Building 404 not found"
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()
# --------------------------------------------------------------------------- #
# delete
# --------------------------------------------------------------------------- #
class TestDelete:
    async def test_deletes_and_commits(self, mock_db, admin_user):
        f = floor()
        stock_db(mock_db, floors=[f])

        result = await floor_router.delete_floor(floor_id=2, db=mock_db, _=admin_user)

        assert result is None
        mock_db.delete.assert_awaited_once_with(f)
        mock_db.commit.assert_awaited_once()

    async def test_missing_floor_raises_404(self, mock_db, admin_user):
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await floor_router.delete_floor(floor_id=99, db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        assert "99" in exc.value.detail
        mock_db.delete.assert_not_awaited()
