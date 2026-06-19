from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from .auth import AuthUser, require_user
from .config import settings
from .db import get_session
from .models import PushSubscription

router = APIRouter(prefix="/push")


class _Keys(BaseModel):
    p256dh: str
    auth: str


class _SubIn(BaseModel):
    endpoint: str
    keys: _Keys


@router.get("/vapid-public-key")
def vapid_public_key() -> dict[str, str]:
    return {"key": settings.vapid_public_key}


@router.post("/subscribe", status_code=204)
def subscribe(
    body: _SubIn,
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    existing = session.exec(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    ).first()
    if existing:
        existing.user_email = user["email"]
        existing.p256dh, existing.auth = body.keys.p256dh, body.keys.auth
        session.add(existing)
    else:
        session.add(
            PushSubscription(
                user_email=user["email"],
                endpoint=body.endpoint,
                p256dh=body.keys.p256dh,
                auth=body.keys.auth,
            )
        )
    session.commit()
