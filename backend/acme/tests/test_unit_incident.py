"""
1. UNIT TESTS: incident router
Each route function is called directly with a mocked AsyncSession.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models import Incident
from app.routers import incident as incident_router
from app.schemas.incident import IncidentBase, IncidentUpdate
from tests.conftest import make_user, result_returning
from app.models import Role

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def _incident(**overrides):
    data = dict(
        id=10, seat_id=1, reported_by=2, status="Open", priority="High", category="Hardware",
        is_escalated=False, incident_notes=None, acknowledged_at=None, resolved_at=None, resolved_by=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def _create_payload(**overrides):
    data = dict(seat_id=1, status="Open", priority="High", category="Hardware",
                is_escalated=False, incident_notes="Monitor flickers")
    data.update(overrides)
    return IncidentBase(**data)


@pytest.fixture
def engineer_user():
    return make_user(id=5, email="eng@acme.inc", role=Role.ENGINEER)


# --------------------------------------------------------------------------- #
# list / mine / get
# --------------------------------------------------------------------------- #
class TestRead:
    async def test_list_returns_all(self, mock_db, employee_user):
        mock_db.execute.return_value = result_returning([_incident(id=1), _incident(id=2)])
        result = await incident_router.list_incidents(db=mock_db, _=employee_user)
        assert [i.id for i in result] == [1, 2]

    async def test_mine_queries_by_current_user(self, mock_db, employee_user):
        mock_db.execute.return_value = result_returning([_incident(reported_by=employee_user.id)])

        result = await incident_router.list_my_incidents(db=mock_db, current_user=employee_user)

        assert len(result) == 1
        sql = str(mock_db.execute.call_args.args[0].compile(compile_kwargs={"literal_binds": True}))
        assert f"reported_by = {employee_user.id}" in sql

    async def test_get_returns_incident(self, mock_db, employee_user):
        mock_db.get.return_value = _incident(id=10)
        result = await incident_router.get_incident(incident_id=10, db=mock_db, _=employee_user)
        assert result.id == 10
        mock_db.get.assert_awaited_once_with(Incident, 10)

    async def test_get_missing_raises_404(self, mock_db, employee_user):
        with pytest.raises(HTTPException) as exc:
            await incident_router.get_incident(incident_id=99, db=mock_db, _=employee_user)
        assert exc.value.status_code == 404


# --------------------------------------------------------------------------- #
# create
# --------------------------------------------------------------------------- #
class TestCreate:
    async def test_reported_by_comes_from_logged_in_user(self, mock_db, employee_user):
        result = await incident_router.create_incident(payload=_create_payload(), db=mock_db, _=employee_user)

        added = mock_db.add.call_args.args[0]
        assert isinstance(added, Incident)
        assert added.reported_by == employee_user.id
        assert added.seat_id == 1
        mock_db.commit.assert_awaited_once()
        assert result is added

    async def test_reported_by_in_payload_is_ignored(self, mock_db, employee_user):
        if "reported_by" not in IncidentBase.model_fields:
            pytest.skip("IncidentBase has no reported_by field")
        payload = _create_payload(reported_by=999)

        await incident_router.create_incident(payload=payload, db=mock_db, _=employee_user)

        assert mock_db.add.call_args.args[0].reported_by == employee_user.id


# --------------------------------------------------------------------------- #
# escalate
# --------------------------------------------------------------------------- #
class TestEscalate:
    async def test_sets_flag_and_commits(self, mock_db, employee_user):
        inc = _incident(is_escalated=False)
        mock_db.get.return_value = inc

        result = await incident_router.escalate_incident(incident_id=10, db=mock_db, _=employee_user)

        assert result.is_escalated is True
        mock_db.commit.assert_awaited_once()

    async def test_missing_raises_404(self, mock_db, employee_user):
        with pytest.raises(HTTPException) as exc:
            await incident_router.escalate_incident(incident_id=99, db=mock_db, _=employee_user)
        assert exc.value.status_code == 404
        mock_db.commit.assert_not_awaited()


# --------------------------------------------------------------------------- #
# update
# --------------------------------------------------------------------------- #
class TestUpdate:
    async def test_applies_only_sent_fields(self, mock_db, engineer_user):
        inc = _incident(priority="High", incident_notes="keep me")
        mock_db.get.return_value = inc

        await incident_router.update_incident(
            incident_id=10, payload=IncidentUpdate(status="In-Progress", acknowledged_at=NOW),
            db=mock_db, current_user=engineer_user,
        )

        assert str(getattr(inc.status, "value", inc.status)) == "In-Progress"
        assert inc.acknowledged_at == NOW
        assert inc.incident_notes == "keep me"   # untouched
        mock_db.execute.assert_not_awaited()      # no resolve -> no engineer lookup

    async def test_missing_raises_404(self, mock_db, engineer_user):
        with pytest.raises(HTTPException) as exc:
            await incident_router.update_incident(
                incident_id=99, payload=IncidentUpdate(status="Open"), db=mock_db, current_user=engineer_user,
            )
        assert exc.value.status_code == 404

    @pytest.mark.parametrize("field", ["status", "priority", "category", "is_escalated"])
    async def test_null_for_required_field_raises_422(self, mock_db, engineer_user, field):
        mock_db.get.return_value = _incident()
        payload = IncidentUpdate.model_validate({field: None})

        with pytest.raises(HTTPException) as exc:
            await incident_router.update_incident(
                incident_id=10, payload=payload, db=mock_db, current_user=engineer_user,
            )

        assert exc.value.status_code == 422
        assert field in exc.value.detail
        mock_db.commit.assert_not_awaited()

    @pytest.mark.parametrize("field", ["acknowledged_at", "resolved_at", "resolved_by", "incident_notes"])
    async def test_null_allowed_for_nullable_fields(self, mock_db, engineer_user, field):
        inc = _incident(**{field: "something"})
        mock_db.get.return_value = inc

        await incident_router.update_incident(
            incident_id=10, payload=IncidentUpdate.model_validate({field: None}),
            db=mock_db, current_user=engineer_user,
        )

        assert getattr(inc, field) is None
        mock_db.commit.assert_awaited_once()

    async def test_resolving_frees_all_engineers_and_credits_current_one(self, mock_db, engineer_user):
        inc = _incident()
        mock_db.get.return_value = inc
        me = SimpleNamespace(id=50, user_id=engineer_user.id, at_incident=10, is_available=False)
        other = SimpleNamespace(id=51, user_id=777, at_incident=10, is_available=False)
        mock_db.execute.return_value = result_returning([me, other])

        await incident_router.update_incident(
            incident_id=10, payload=IncidentUpdate(status="Resolved", resolved_at=NOW),
            db=mock_db, current_user=engineer_user,
        )

        assert inc.resolved_by == me.id
        for eng in (me, other):
            assert eng.at_incident is None
            assert eng.is_available is True

    async def test_explicit_resolved_by_is_not_overwritten(self, mock_db, engineer_user):
        inc = _incident()
        mock_db.get.return_value = inc
        me = SimpleNamespace(id=50, user_id=engineer_user.id, at_incident=10, is_available=False)
        mock_db.execute.return_value = result_returning([me])

        await incident_router.update_incident(
            incident_id=10, payload=IncidentUpdate(resolved_at=NOW, resolved_by=123),
            db=mock_db, current_user=engineer_user,
        )

        assert inc.resolved_by == 123
        assert me.is_available is True

    async def test_admin_resolving_without_engineer_record_leaves_resolved_by_empty(self, mock_db, admin_user):
        inc = _incident()
        mock_db.get.return_value = inc
        mock_db.execute.return_value = result_returning([])

        await incident_router.update_incident(
            incident_id=10, payload=IncidentUpdate(resolved_at=NOW), db=mock_db, current_user=admin_user,
        )

        assert inc.resolved_by is None
        assert inc.resolved_at == NOW


# --------------------------------------------------------------------------- #
# delete
# --------------------------------------------------------------------------- #
class TestDelete:
    async def test_deletes_and_commits(self, mock_db, admin_user):
        inc = _incident()
        mock_db.get.return_value = inc

        result = await incident_router.delete_incident(incident_id=10, db=mock_db, _=admin_user)

        assert result is None
        mock_db.delete.assert_awaited_once_with(inc)
        mock_db.commit.assert_awaited_once()

    async def test_missing_raises_404(self, mock_db, admin_user):
        with pytest.raises(HTTPException) as exc:
            await incident_router.delete_incident(incident_id=99, db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        mock_db.delete.assert_not_awaited()
