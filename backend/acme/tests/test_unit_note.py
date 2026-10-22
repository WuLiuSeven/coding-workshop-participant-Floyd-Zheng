"""
1. UNIT TESTS: note router
Each route function is called directly with a mocked AsyncSession.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models import Incident, Note, Role
from app.routers import note as note_router
from app.schemas.note import NoteBase, NoteUpdate
from tests.conftest import make_user, result_returning


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def note(**kw):
    data = dict(id=4, incident_at=10, comments="Replaced the cable")
    data.update(kw)
    return SimpleNamespace(**data)


def incident(**kw):
    data = dict(id=10)
    data.update(kw)
    return SimpleNamespace(**data)


def stock_db(mock_db, incidents=(), notes=()):
    """Make db.get(Model, id) return the matching fake row (or None)."""
    rows = {Incident: {i.id: i for i in incidents}, Note: {n.id: n for n in notes}}
    mock_db.get = AsyncMock(side_effect=lambda model, pk: rows.get(model, {}).get(pk))


def create_payload(**kw):
    data = dict(incident_at=10, comments="Replaced the cable")
    data.update(kw)
    return NoteBase(**data)


# --------------------------------------------------------------------------- #
# list / get
# --------------------------------------------------------------------------- #
class TestRead:
    async def test_list_returns_all(self, mock_db, employee_user):
        mock_db.execute.return_value = result_returning([note(id=1), note(id=2)])
        result = await note_router.list_notes(db=mock_db, _=employee_user)
        assert [n.id for n in result] == [1, 2]

    async def test_list_empty(self, mock_db, employee_user):
        mock_db.execute.return_value = result_returning([])
        assert await note_router.list_notes(db=mock_db, _=employee_user) == []

    async def test_get_returns_note(self, mock_db, employee_user):
        stock_db(mock_db, notes=[note(id=4)])
        result = await note_router.get_note(note_id=4, db=mock_db, _=employee_user)
        assert result.comments == "Replaced the cable"

    async def test_get_missing_raises_404(self, mock_db, employee_user):
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await note_router.get_note(note_id=99, db=mock_db, _=employee_user)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Note 99 not found"


# --------------------------------------------------------------------------- #
# create (any logged-in user)
# --------------------------------------------------------------------------- #
class TestCreate:
    async def test_creates_note_on_existing_incident(self, mock_db, employee_user):
        stock_db(mock_db, incidents=[incident(id=10)])

        result = await note_router.create_note(payload=create_payload(), db=mock_db, _=employee_user)

        added = mock_db.add.call_args.args[0]
        assert isinstance(added, Note)
        assert (added.incident_at, added.comments) == (10, "Replaced the cable")
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(added)
        assert result is added

    async def test_engineer_can_create(self, mock_db):
        stock_db(mock_db, incidents=[incident(id=10)])
        eng = make_user(id=5, role=Role.ENGINEER)

        await note_router.create_note(payload=create_payload(), db=mock_db, _=eng)

        mock_db.commit.assert_awaited_once()

    async def test_missing_incident_raises_404(self, mock_db, employee_user):
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await note_router.create_note(payload=create_payload(incident_at=404), db=mock_db, _=employee_user)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Incident 404 not found"
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()


# --------------------------------------------------------------------------- #
# update (admin only)
# --------------------------------------------------------------------------- #
class TestUpdate:
    async def test_edits_comment_only(self, mock_db, admin_user):
        n = note(comments="old")
        stock_db(mock_db, notes=[n])

        result = await note_router.update_note(
            note_id=4, payload=NoteUpdate(comments="new"), db=mock_db, _=admin_user,
        )

        assert result.comments == "new"
        assert result.incident_at == 10
        mock_db.commit.assert_awaited_once()

    async def test_moves_note_to_another_existing_incident(self, mock_db, admin_user):
        n = note(incident_at=10)
        stock_db(mock_db, incidents=[incident(id=10), incident(id=11)], notes=[n])

        await note_router.update_note(note_id=4, payload=NoteUpdate(incident_at=11), db=mock_db, _=admin_user)

        assert n.incident_at == 11

    async def test_missing_note_raises_404(self, mock_db, admin_user):
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await note_router.update_note(note_id=99, payload=NoteUpdate(comments="x"), db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Note 99 not found"

    async def test_unknown_incident_raises_404_and_keeps_note(self, mock_db, admin_user):
        n = note(incident_at=10)
        stock_db(mock_db, notes=[n])
        with pytest.raises(HTTPException) as exc:
            await note_router.update_note(note_id=4, payload=NoteUpdate(incident_at=404), db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Incident 404 not found"
        assert n.incident_at == 10
        mock_db.commit.assert_not_awaited()

    async def test_null_incident_raises_422(self, mock_db, admin_user):
        n = note()
        stock_db(mock_db, notes=[n])
        with pytest.raises(HTTPException) as exc:
            await note_router.update_note(
                note_id=4, payload=NoteUpdate.model_validate({"incident_at": None}), db=mock_db, _=admin_user,
            )
        assert exc.value.status_code == 422
        assert n.incident_at == 10
        mock_db.commit.assert_not_awaited()

    async def test_empty_update_is_a_no_op(self, mock_db, admin_user):
        n = note()
        stock_db(mock_db, notes=[n])
        result = await note_router.update_note(note_id=4, payload=NoteUpdate(), db=mock_db, _=admin_user)
        assert (result.incident_at, result.comments) == (10, "Replaced the cable")

    async def test_null_comment_raises_422(self, mock_db, admin_user):
        n = note()
        stock_db(mock_db, notes=[n])
        with pytest.raises(HTTPException) as exc:
            await note_router.update_note(
                note_id=4, payload=NoteUpdate.model_validate({"comments": None}), db=mock_db, _=admin_user,
            )
        assert exc.value.status_code == 422


# --------------------------------------------------------------------------- #
# delete (admin only)
# --------------------------------------------------------------------------- #
class TestDelete:
    async def test_deletes_and_commits(self, mock_db, admin_user):
        n = note()
        stock_db(mock_db, notes=[n])

        result = await note_router.delete_note(note_id=4, db=mock_db, _=admin_user)

        assert result is None
        mock_db.delete.assert_awaited_once_with(n)
        mock_db.commit.assert_awaited_once()

    async def test_missing_note_raises_404(self, mock_db, admin_user):
        stock_db(mock_db)
        with pytest.raises(HTTPException) as exc:
            await note_router.delete_note(note_id=99, db=mock_db, _=admin_user)
        assert exc.value.status_code == 404
        mock_db.delete.assert_not_awaited()
