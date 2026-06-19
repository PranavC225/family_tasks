import json

from pywebpush import WebPushException, webpush
from sqlmodel import Session, col, select

from .config import settings
from .db import engine
from .models import PushSubscription


def _send(sub: PushSubscription, payload: str) -> bool:
    """Send one push. Return False if the subscription is gone and should be pruned."""
    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=payload,
            vapid_private_key=settings.vapid_private_key_pem,
            vapid_claims={"sub": settings.vapid_subject},
        )
        return True
    except WebPushException as exc:
        status = exc.response.status_code if exc.response is not None else None
        return status not in (404, 410)  # 404/410 => dead, prune; else keep


def notify(emails: list[str], title: str, body: str, url: str = "/tasks") -> None:
    """Fan out a notification to all device subscriptions for the given users.

    Opens its own session — it runs as a BackgroundTask after the request session closes.
    """
    if not emails or not settings.vapid_private_key:
        return
    payload = json.dumps({"title": title, "body": body, "url": url})
    with Session(engine) as session:
        subs = session.exec(
            select(PushSubscription).where(col(PushSubscription.user_email).in_(emails))
        ).all()
        for sub in subs:
            if not _send(sub, payload):
                session.delete(sub)
        session.commit()
