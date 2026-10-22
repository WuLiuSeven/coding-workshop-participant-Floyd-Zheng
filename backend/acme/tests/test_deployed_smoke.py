"""
SMOKE TESTS against the deployed stack (CloudFront -> Lambda -> Postgres).

Opt-in only, and read-only: every request here is rejected before it can
write anything, so it is safe to run against the live environment.

    RUN_DEPLOYED_TESTS=1 pytest -m deployed

Override the target with ACME_API_URL, e.g. to hit the Lambda URL directly:
    ACME_API_URL=https://7et5ejqd5jj6xbtyvkxmhxwbsm0fswpx.lambda-url.us-east-2.on.aws
"""
import os

import httpx
import pytest

BASE_URL = os.environ.get("ACME_API_URL", "https://d1x3h8lxxcvki9.cloudfront.net/api/acme").rstrip("/")

pytestmark = [
    pytest.mark.deployed,
    pytest.mark.skipif(os.environ.get("RUN_DEPLOYED_TESTS") != "1", reason="set RUN_DEPLOYED_TESTS=1"),
]


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=BASE_URL, timeout=30) as c:
        yield c


def test_list_users_requires_auth(http):
    assert http.get("/auth").status_code == 401


def test_login_with_bad_credentials_returns_401(http):
    r = http.post("/auth/token", data={"username": "nobody@acme.inc", "password": "definitely-wrong"})
    assert r.status_code == 401


def test_register_employee_rejects_non_acme_email(http):
    r = http.post(
        "/auth/registerEmployee",
        json={"email": "smoke@example.com", "password": "x", "first_name": "S", "last_name": "T", "role": "Employee"},
    )
    assert r.status_code in (400, 422)


def test_unknown_route_returns_404(http):
    assert http.get("/does-not-exist").status_code == 404
