"""
1. UNIT TESTS: ticket router
Each route function is called directly with a mocked AsyncSession.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models import Engineer, Incident, Role, Ticket
from app.routers import ticket as ticket_router
from app.schemas.ticket import TicketBase, TicketUpdate
from tests.conftest import make_user, result_returning

CREATED = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def engineer(**kw):
    data = dict(id=3, user_id=5, at_incident=None, is_available=True)
    data.update(kw)
    return SimpleNamespace(**data)


def incident(**kw):
    data = dict(id=10, acknowledged_at=None, resolved_at=None, reported_by=2)
    data.update(kw)
    return SimpleNamespace(**data)


def ticket(**kw):
    data = dict(id=7, engineer_id=3, incident_id=10, created_at=CREATED)
    data.update(kw)
    return SimpleNamespace(**data)


def stock_db(mock_db, engineers=(), incidents=(), tickets=()):
    """Make db.get(Model, id) return the matching fake row (or None)."""
    rows = {
        Engineer: {e.id: e for e in engineers},
        Incident: {i.id: i for i in incidents},
        Ticket: {t.id: t for t in tickets},
    }
    mock_db.get = AsyncMock(side_effect=lambda model, pk: rows.get(model, {}).get(pk))


def create_payload(**kw):
    data = dict(engineer_id=3, incident_id=10)
    data.update(kw)
    return TicketBase(**data)


def compiled_sql(mock_db):
    stmt = mock_db.execute.call_args.args[0]
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


@pytest.fixture
def engineer_user():
    return make_user(id=5, email="eng@acme.inc", role=Role.ENGINEER)


@pytest.fixture
def db_sets_created_at(mock_db):
    """refresh() fills in DB-generated id + created_at, like Postgres would."""
    async def _refresh(obj):
        if getattr(obj, "id", None) is None:
            obj.id = 99
        if getattr(obj, "created_at", None) is None:
            obj.created_at = CREATED
    mock_db.refresh = AsyncMock(side_effect=_refresh)
    return mock_db


# --------------------------------------------------------------------------- #
# list / mine / get
# --------------------------------------------------------------------------- #
class TestRead:
    async def test_list_returns_all(self, mock_db, employee_user):
        mock_db.execute.return_value = result_returning([ticket(id=1), ticket(id=2)])
        result = await ticket_router.list_tickets(db=mock_db, _=employee_user)
        assert [t.id for t in result] == [1, 2]

    async def test_mine_for_engineer_filters_by_assigned_engineer(self, mock_db, engineer_user):
        mock_db.execute.return_value = result_returning([ticket()])

        result = await ticket_router.list_my_tickets(db=mock_db, current_user=engineer_user)

        assert len(result) == 1
        sql = compiled_sql(mock_db)
        assert f"user_id = {engineer_user.id}" in sql
        assert "reported_by" not in sql

    @pytest.mark.parametrize("role", [Role.EMPLOYEE, Role.FACILITY_ADMIN])
    async def test_mine_for_others_filters_by_reporter(self, mock_db, role):
        user = make_user(id=2, role=role)
        mock_db.execute.return_value = result_returning([])

        await ticket_router.list_my_tickets(db=mock_db, current_user=user)

        sql = compiled_sql(mock_db)
        assert f"reported_by = {user.id}" in sql
        assert "user_id" not in sql

    async def test_get_returns_ticket(self, mock_db, employee_user):
        stock_db(mock_db, tickets=[ticket(id=7)])
        result = await ticket_router.get_ticket(ticket_id=7, db=mock_db, _=employee_user)
        assert result.id == 7

    async def test_get_missing_raises_404(self, mock_db, employee_user):
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await ticket_router.get_ticket(ticket_id=99, db=mock_db, _=employee_user)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Ticket 99 not found"


# --------------------------------------------------------------------------- #
# create
# --------------------------------------------------------------------------- #
class TestCreate:
    async def test_assigns_engineer_to_incident(self, db_sets_created_at, admin_user):
        eng, inc = engineer(), incident(acknowledged_at=EARLIER)
        stock_db(db_sets_created_at, engineers=[eng], incidents=[inc])

        result = await ticket_router.create_ticket(payload=create_payload(), db=db_sets_created_at, _=admin_user)

        added = db_sets_created_at.add.call_args.args[0]
        assert isinstance(added, Ticket)
        assert (added.engineer_id, added.incident_id) == (3, 10)
        assert eng.at_incident == 10
        assert eng.is_available is False
        assert result is added

    async def test_first_ticket_acknowledges_incident(self, db_sets_created_at, admin_user):
        inc = incident(acknowledged_at=None)
        stock_db(db_sets_created_at, engineers=[engineer()], incidents=[inc])

        await ticket_router.create_ticket(payload=create_payload(), db=db_sets_created_at, _=admin_user)

        assert inc.acknowledged_at == CREATED          # = the ticket's created_at
        assert db_sets_created_at.commit.await_count == 2

    async def test_later_ticket_keeps_original_acknowledgement(self, db_sets_created_at, admin_user):
        inc = incident(acknowledged_at=EARLIER)
        stock_db(db_sets_created_at, engineers=[engineer()], incidents=[inc])

        await ticket_router.create_ticket(payload=create_payload(), db=db_sets_created_at, _=admin_user)

        assert inc.acknowledged_at == EARLIER
        assert db_sets_created_at.commit.await_count == 1

    async def test_missing_engineer_raises_404(self, mock_db, admin_user):
        stock_db(mock_db, incidents=[incident()])
        with pytest.raises(HTTPException) as exc:
            await ticket_router.create_ticket(payload=create_payload(engineer_id=404), db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        assert "Engineer 404" in exc.value.detail
        mock_db.add.assert_not_called()

    async def test_missing_incident_raises_404(self, mock_db, admin_user):
        eng = engineer()
        stock_db(mock_db, engineers=[eng])
        with pytest.raises(HTTPException) as exc:
            await ticket_router.create_ticket(payload=create_payload(incident_id=404), db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        assert "Incident 404" in exc.value.detail
        assert eng.is_available is True        # engineer untouched
        mock_db.add.assert_not_called()

    async def test_resolved_incident_raises_409(self, mock_db, admin_user):
        eng = engineer()
        stock_db(mock_db, engineers=[eng], incidents=[incident(resolved_at=CREATED)])
        with pytest.raises(HTTPException) as exc:
            await ticket_router.create_ticket(payload=create_payload(), db=mock_db, _=admin_user)
        assert exc.value.status_code == 409
        assert eng.is_available is True
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()



# --------------------------------------------------------------------------- #
# update
# --------------------------------------------------------------------------- #
class TestUpdate:
    async def test_reassigns_to_existing_engineer(self, mock_db, admin_user):
        t = ticket(engineer_id=3)
        stock_db(mock_db, engineers=[engineer(id=3), engineer(id=4, user_id=6)], tickets=[t])

        result = await ticket_router.update_ticket(
            ticket_id=7, payload=TicketUpdate(engineer_id=4), db=mock_db, _=admin_user,
        )

        assert result.engineer_id == 4
        assert result.incident_id == 10      # untouched
        mock_db.commit.assert_awaited_once()

    async def test_moves_to_existing_incident(self, mock_db, admin_user):
        t = ticket(incident_id=10)
        stock_db(mock_db, incidents=[incident(id=10), incident(id=11)], tickets=[t])

        await ticket_router.update_ticket(ticket_id=7, payload=TicketUpdate(incident_id=11), db=mock_db, _=admin_user)

        assert t.incident_id == 11

    async def test_missing_ticket_raises_404(self, mock_db, admin_user):
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await ticket_router.update_ticket(ticket_id=99, payload=TicketUpdate(engineer_id=3), db=mock_db, _=admin_user)
        assert exc.value.status_code == 404

    async def test_unknown_engineer_raises_404_and_keeps_old_value(self, mock_db, admin_user):
        t = ticket(engineer_id=3)
        stock_db(mock_db, tickets=[t])
        with pytest.raises(HTTPException) as exc:
            await ticket_router.update_ticket(ticket_id=7, payload=TicketUpdate(engineer_id=404), db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        assert t.engineer_id == 3
        mock_db.commit.assert_not_awaited()

    async def test_unknown_incident_raises_404(self, mock_db, admin_user):
        t = ticket(incident_id=10)
        stock_db(mock_db, tickets=[t])
        with pytest.raises(HTTPException) as exc:
            await ticket_router.update_ticket(ticket_id=7, payload=TicketUpdate(incident_id=404), db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        assert t.incident_id == 10

    @pytest.mark.parametrize("field", ["engineer_id", "incident_id"])
    async def test_null_raises_422(self, mock_db, admin_user, field):
        stock_db(mock_db, tickets=[ticket()])
        with pytest.raises(HTTPException) as exc:
            await ticket_router.update_ticket(
                ticket_id=7, payload=TicketUpdate.model_validate({field: None}), db=mock_db, _=admin_user,
            )
        assert exc.value.status_code == 422
        assert field in exc.value.detail
        mock_db.commit.assert_not_awaited()

    async def test_empty_update_is_a_no_op(self, mock_db, admin_user):
        t = ticket()
        stock_db(mock_db, tickets=[t])
        result = await ticket_router.update_ticket(ticket_id=7, payload=TicketUpdate(), db=mock_db, _=admin_user)
        assert (result.engineer_id, result.incident_id) == (3, 10)

# --------------------------------------------------------------------------- #
# delete
# --------------------------------------------------------------------------- #
class TestDelete:
    async def test_frees_engineer_working_on_that_incident(self, mock_db, admin_user):
        eng = engineer(at_incident=10, is_available=False)
        t = ticket()
        stock_db(mock_db, engineers=[eng], tickets=[t])

        result = await ticket_router.delete_ticket(ticket_id=7, db=mock_db, _=admin_user)

        assert result is None
        assert (eng.at_incident, eng.is_available) == (None, True)
        mock_db.delete.assert_awaited_once_with(t)
        mock_db.commit.assert_awaited_once()

    async def test_leaves_engineer_alone_if_now_on_another_incident(self, mock_db, admin_user):
        eng = engineer(at_incident=55, is_available=False)
        stock_db(mock_db, engineers=[eng], tickets=[ticket()])

        await ticket_router.delete_ticket(ticket_id=7, db=mock_db, _=admin_user)

        assert (eng.at_incident, eng.is_available) == (55, False)

    async def test_works_when_engineer_record_is_gone(self, mock_db, admin_user):
        t = ticket()
        stock_db(mock_db, tickets=[t])

        await ticket_router.delete_ticket(ticket_id=7, db=mock_db, _=admin_user)

        mock_db.delete.assert_awaited_once_with(t)

    async def test_missing_ticket_raises_404(self, mock_db, admin_user):
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await ticket_router.delete_ticket(ticket_id=99, db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        mock_db.delete.assert_not_awaited()
