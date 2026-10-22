"""
2. INTEGRATION TESTS: incident router against a real Postgres database.
Same setup as test_integration_auth.py (TEST_DATABASE_URL, throwaway DB only).

A real seat is built first through the API: facility -> building -> floor -> seat.
"""
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from tests.test_integration_auth import (  # noqa: F401  (fixtures are used by name)
    TEST_DATABASE_URL, _auth, _seed_user, admin_headers, client, session_factory,
)
from app.models import Role

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set"),
]


def _iso(dt=None):
    return (dt or datetime.now(timezone.utc)).isoformat()


async def _post_ok(client, path, headers, body):
    r = await client.post(path, headers=headers, json=body)
    assert r.status_code in (200, 201), f"POST {path} -> {r.status_code}: {r.text}"
    return r.json()["id"]


@pytest_asyncio.fixture
async def seat_id(client, admin_headers):
    facility = await _post_ok(client, "/facility", admin_headers, {"name": "HQ"})
    building = await _post_ok(client, "/building", admin_headers, {"name": "Tower A", "facility_id": facility})
    floor = await _post_ok(client, "/floor", admin_headers, {"floor_number": 3, "building_id": building})
    return await _post_ok(client, "/seat", admin_headers, {"seat_number": 42, "floor_id": floor})


@pytest_asyncio.fixture
async def employee(session_factory):
    user_id = await _seed_user(session_factory, "emp@acme.inc", Role.EMPLOYEE)
    return user_id, _auth("emp@acme.inc", Role.EMPLOYEE)


@pytest_asyncio.fixture
async def engineer_headers(session_factory):
    await _seed_user(session_factory, "eng@acme.inc", Role.ENGINEER)
    return _auth("eng@acme.inc", Role.ENGINEER)


def _new_incident(seat_id, **overrides):
    body = {"seat_id": seat_id, "status": "Open", "priority": "High", "category": "Hardware",
            "is_escalated": False, "incident_notes": "Monitor flickers"}
    body.update(overrides)
    return body


async def _report(client, headers, seat_id, **overrides):
    r = await client.post("/incident", headers=headers, json=_new_incident(seat_id, **overrides))
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
async def test_employee_reports_incident(client, seat_id, employee):
    user_id, headers = employee

    body = await _report(client, headers, seat_id)

    assert body["seat_id"] == seat_id
    assert body["reported_by"] == user_id
    assert body["is_escalated"] is False
    assert body["created_at"]                       # server default now()
    assert body["acknowledged_at"] is None
    assert body["resolved_at"] is None


async def test_mine_only_returns_own_incidents(client, seat_id, employee, admin_headers):
    _, emp_headers = employee
    mine = await _report(client, emp_headers, seat_id)
    await _report(client, admin_headers, seat_id, category="Software")

    r = await client.get("/incident/mine", headers=emp_headers)
    assert r.status_code == 200
    assert [i["id"] for i in r.json()] == [mine["id"]]

    r = await client.get("/incident", headers=emp_headers)
    assert len(r.json()) == 2   # the full list is visible to everyone


async def test_anyone_can_escalate(client, seat_id, employee):
    _, headers = employee
    inc = await _report(client, headers, seat_id)

    r = await client.patch(f"/incident/{inc['id']}/escalate", headers=headers)

    assert r.status_code == 200
    assert r.json()["is_escalated"] is True
    assert (await client.get(f"/incident/{inc['id']}", headers=headers)).json()["is_escalated"] is True


async def test_full_lifecycle_and_timings(client, seat_id, employee, engineer_headers, admin_headers):
    _, emp_headers = employee
    inc = await _report(client, emp_headers, seat_id)

    # engineer acknowledges
    acked = _iso()
    r = await client.patch(f"/incident/{inc['id']}", headers=engineer_headers,
                           json={"status": "In_Progress", "acknowledged_at": acked})
    assert r.status_code == 200
    assert r.json()["status"] == "In_Progress"
    assert r.json()["acknowledged_at"] is not None

    # engineer resolves
    r = await client.patch(f"/incident/{inc['id']}", headers=engineer_headers,
                           json={"status": "Resolved", "resolved_at": _iso()})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "Resolved"

    # the timestamps the analytics panel relies on are in order
    created = datetime.fromisoformat(body["created_at"])
    acknowledged = datetime.fromisoformat(body["acknowledged_at"])
    resolved = datetime.fromisoformat(body["resolved_at"])
    assert created <= acknowledged <= resolved

    # admin deletes
    assert (await client.delete(f"/incident/{inc['id']}", headers=admin_headers)).status_code == 204
    assert (await client.get(f"/incident/{inc['id']}", headers=admin_headers)).status_code == 404


async def test_partial_update_keeps_other_fields(client, seat_id, employee, engineer_headers):
    _, emp_headers = employee
    inc = await _report(client, emp_headers, seat_id, incident_notes="keep me")

    r = await client.patch(f"/incident/{inc['id']}", headers=engineer_headers, json={"priority": "Low"})

    assert r.status_code == 200
    assert r.json()["priority"] == "Low"
    assert r.json()["incident_notes"] == "keep me"
    assert r.json()["category"] == "Hardware"


async def test_reopening_clears_resolved_at(client, seat_id, employee, admin_headers):
    _, emp_headers = employee
    inc = await _report(client, emp_headers, seat_id)
    await client.patch(f"/incident/{inc['id']}", headers=admin_headers,
                       json={"status": "Resolved", "acknowledged_at": _iso(), "resolved_at": _iso()})

    r = await client.patch(f"/incident/{inc['id']}", headers=admin_headers,
                           json={"status": "Open", "resolved_at": None})

    assert r.status_code == 200
    assert r.json()["resolved_at"] is None


async def test_employee_cannot_update_or_delete(client, seat_id, employee):
    _, headers = employee
    inc = await _report(client, headers, seat_id)

    assert (await client.patch(f"/incident/{inc['id']}", headers=headers,
                               json={"status": "Resolved"})).status_code == 403
    assert (await client.delete(f"/incident/{inc['id']}", headers=headers)).status_code == 403


# --------------------------------------------------------------------------- #
# Known gaps (expected to fail until the router is changed)
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(reason="create_incident doesn't check the seat exists; the FK error surfaces as a 500")
async def test_reporting_on_missing_seat_returns_4xx(client, employee):
    _, headers = employee
    r = await client.post("/incident", headers=headers, json=_new_incident(seat_id=999_999))
    assert r.status_code in (400, 404, 422)


@pytest.mark.xfail(reason="escalate_incident allows escalating an already-resolved incident")
async def test_cannot_escalate_resolved_incident(client, seat_id, employee, admin_headers):
    _, headers = employee
    inc = await _report(client, headers, seat_id)
    await client.patch(f"/incident/{inc['id']}", headers=admin_headers,
                       json={"status": "Resolved", "resolved_at": _iso()})

    r = await client.patch(f"/incident/{inc['id']}/escalate", headers=headers)
    assert r.status_code in (400, 409)
