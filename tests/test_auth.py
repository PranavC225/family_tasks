from fastapi.testclient import TestClient

from family_tasks import auth
from family_tasks.config import settings


def _mock_token(email: str, name: str = "Test User"):
    async def _fake(request):
        return {"userinfo": {"email": email, "name": name, "picture": None}}

    return _fake


def test_allowlisted_email_sets_session_and_redirects(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "allowed_emails", "person1@gmail.com")
    monkeypatch.setattr(auth.oauth.google, "authorize_access_token", _mock_token("Person1@Gmail.com"))

    r = client.get("/auth/callback")

    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert "session" in r.cookies


def test_non_allowlisted_email_rejected(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "allowed_emails", "person1@gmail.com")
    monkeypatch.setattr(auth.oauth.google, "authorize_access_token", _mock_token("stranger@gmail.com"))

    r = client.get("/auth/callback")

    assert r.status_code == 403
    assert "session" not in r.cookies


def test_protected_get_redirects_to_login_when_logged_out(client: TestClient) -> None:
    r = client.get("/tasks", headers={"accept": "text/html"})

    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_dev_login_404_in_production(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "env", "production")

    r = client.get("/auth/dev-login")

    assert r.status_code == 404
