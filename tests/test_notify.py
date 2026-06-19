import pytest
from fastapi.testclient import TestClient
from pywebpush import WebPushException
from sqlmodel import Session, select

from conftest import test_engine
from family_tasks import push
from family_tasks.models import PushSubscription
from family_tasks.tasks import recipients_for


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def test_recipients_for_assignee_other_than_creator() -> None:
    assert recipients_for("a@x.com", "b@x.com", {"a@x.com", "b@x.com"}) == ["b@x.com"]


def test_recipients_for_assignee_is_creator_returns_empty() -> None:
    assert recipients_for("a@x.com", "a@x.com", {"a@x.com", "b@x.com"}) == []


def test_recipients_for_general_task_excludes_creator() -> None:
    allowlist = {"a@x.com", "b@x.com", "c@x.com"}
    assert recipients_for("a@x.com", None, allowlist) == ["b@x.com", "c@x.com"]


def test_subscribe_creates_row(logged_in_client: TestClient) -> None:
    r = logged_in_client.post(
        "/push/subscribe",
        json={"endpoint": "https://push.example/abc", "keys": {"p256dh": "p", "auth": "a"}},
    )
    assert r.status_code == 204
    with Session(test_engine) as session:
        rows = list(session.exec(select(PushSubscription)).all())
    assert len(rows) == 1
    assert rows[0].user_email == "dev@example.com"


def test_subscribe_same_endpoint_upserts(logged_in_client: TestClient) -> None:
    body = {"endpoint": "https://push.example/same", "keys": {"p256dh": "p", "auth": "a"}}
    logged_in_client.post("/push/subscribe", json=body)
    body["keys"]["auth"] = "a2"
    logged_in_client.post("/push/subscribe", json=body)
    with Session(test_engine) as session:
        rows = list(session.exec(select(PushSubscription)).all())
    assert len(rows) == 1
    assert rows[0].auth == "a2"


def test_notify_prunes_dead_subscription(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(push, "engine", test_engine)
    with Session(test_engine) as session:
        session.add(
            PushSubscription(
                user_email="dev@example.com",
                endpoint="https://push.example/dead",
                p256dh="p",
                auth="a",
            )
        )
        session.commit()

    def _raise(*args: object, **kwargs: object) -> None:
        raise WebPushException("gone", response=_FakeResponse(410))  # type: ignore[arg-type]

    monkeypatch.setattr(push, "webpush", _raise)
    push.notify(["dev@example.com"], "title", "body")

    with Session(test_engine) as session:
        rows = list(session.exec(select(PushSubscription)).all())
    assert rows == []
