from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    active = "active"
    done = "done"
    archived = "archived"


class User(SQLModel, table=True):
    email: str = Field(primary_key=True)
    display_name: str
    picture_url: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    notes: str | None = None
    status: TaskStatus = Field(default=TaskStatus.active, index=True)
    is_recurring: bool = Field(default=False)
    created_by_email: str = Field(index=True)
    created_by_name: str
    assigned_to_email: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
    archived_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utcnow)


class PushSubscription(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_email: str = Field(index=True)
    endpoint: str = Field(unique=True)
    p256dh: str
    auth: str
    created_at: datetime = Field(default_factory=utcnow)
