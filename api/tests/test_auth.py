from fastapi import Depends

from app.auth import require_admin
from app.main import app


# Registered once at import time. Registering inside a test body would make the
# second test depend on the first having run, which breaks under -k.
def _register_probe_route() -> None:
    if any(getattr(r, "path", None) == "/_test_admin_only" for r in app.routes):
        return

    @app.get("/_test_admin_only")
    def _admin_only(_=Depends(require_admin)):
        return {"ok": True}


_register_probe_route()


def test_login_returns_token_and_role(api, users):
    response = api.post("/auth/login", json={"email": "admin@peblo.test", "password": "pw"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"
    assert body["access_token"]


def test_login_with_wrong_password_is_rejected(api, users):
    response = api.post("/auth/login", json={"email": "admin@peblo.test", "password": "nope"})
    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "invalid_credentials"


def test_login_with_unknown_email_is_rejected(api, users):
    response = api.post("/auth/login", json={"email": "nobody@peblo.test", "password": "pw"})
    assert response.status_code == 401


def test_me_requires_a_token(api, users):
    assert api.get("/auth/me").status_code == 401


def test_me_rejects_a_forged_token(api, users):
    response = api.get("/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert response.status_code == 401


def test_me_returns_the_caller(api, editor_headers):
    response = api.get("/auth/me", headers=editor_headers)
    assert response.status_code == 200
    assert response.json()["role"] == "editor"


def test_require_admin_rejects_an_editor(api, editor_headers):
    response = api.get("/_test_admin_only", headers=editor_headers)
    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "forbidden"


def test_require_admin_rejects_an_anonymous_caller(api, users):
    assert api.get("/_test_admin_only").status_code == 401


def test_require_admin_allows_an_admin(api, admin_headers):
    response = api.get("/_test_admin_only", headers=admin_headers)
    assert response.status_code == 200
