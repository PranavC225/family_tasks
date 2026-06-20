import json
import logging

from py_vapid import Vapid
from pywebpush import WebPushException, webpush
from sqlmodel import Session, col, select

from .config import settings
from .db import engine
from .models import PushSubscription

logger = logging.getLogger(__name__)


def _send(sub: PushSubscription, payload: str, vapid: Vapid) -> bool:
    """Send one push. Return False if the subscription is gone and should be pruned."""
    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=payload,
            vapid_private_key=vapid,
            vapid_claims={"sub": settings.vapid_subject_claim},
        )
        return True
    except WebPushException as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in (404, 410):
            return False  # dead, prune
        logger.warning("web push failed for %s: %s", sub.endpoint, exc)
        return True  # transient — keep the subscription
    except Exception:
        logger.exception("unexpected web push error for %s", sub.endpoint)
        return True  # our bug, not a dead endpoint — keep it


def notify(emails: list[str], title: str, body: str, url: str = "/tasks") -> None:
    """Fan out a notification to all device subscriptions for the given users.

    Opens its own session — it runs as a BackgroundTask after the request session closes.
    """
    if not emails or not settings.vapid_private_key:
        return
    try:
        vapid = Vapid.from_pem(settings.vapid_private_key_pem.encode())
    except Exception:
        logger.exception("invalid VAPID_PRIVATE_KEY; cannot send push notifications")
        return
    payload = json.dumps({"title": title, "body": body, "url": url})
    with Session(engine) as session:
        subs = session.exec(
            select(PushSubscription).where(col(PushSubscription.user_email).in_(emails))
        ).all()
        for sub in subs:
            if not _send(sub, payload, vapid):
                session.delete(sub)
        session.commit()
