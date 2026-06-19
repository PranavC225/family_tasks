# family-tasks — Implementation Plan (Handoff to Sonnet)

> **Read this entire file before writing any code.** This plan was authored by Opus after a
> First-Principles / IterativeDepth / Council / BeCreative brainstorm and two rounds of decisions
> with the user. The architecture is **locked**. Your job (Sonnet) is to implement it faithfully,
> phase by phase, ticking the checklists. Do **not** redesign, add scope, or substitute libraries
> without flagging it to the user first.

---

## 0. What we're building (the irreducible core)

A **shared task list for exactly 4 family members**. Not a Todoist clone — no projects, priorities,
due dates, or notifications in v1. The entire app is *shared state for 4 trusted people* over a
three-state task lifecycle:

```
              complete                 archive
  ACTIVE ───────────────▶ DONE ───────────────▶ ARCHIVED
    ▲                       │                       │
    │      reactivate       │                       │  unarchive
    └───────────────────────┘◀──────────────────────┘
                  archive (active → archived also allowed)
```

- **Active** — the main list everyone sees.
- **Done** — completed tasks disappear from the active list but are **kept** (not deleted). This is
  the user's "deleted from the list" requirement: gone from *Active*, retained in *Done*.
- **Reactivate** — flip a Done task back to Active. This *is* the "repetitive tasks can be
  reactivated" requirement. No scheduler, no cron — purely manual for v1.
- **Archived** — "permanent storage." A separate view, kept indefinitely. Any task can be moved here.

**Design constraints (from the user, non-negotiable):**
- Access restricted to **4 people**, enforced by a server-side email allowlist (not obscurity).
- **Free forever, zero maintenance fees.** Verified June 2026: Cloud Run free tier (2M req/mo) does
  not expire; Neon free tier (0.5 GB, scale-to-zero) is perpetual for low-traffic apps. Our data is
  kilobytes — comfortably inside both.
- **Containerized** (a Dockerfile that runs on Cloud Run).
- **Mobile-first.** The family uses phones. Add-a-task = one field + one big button. Friction kills
  adoption.

---

## 1. Locked stack & hosting

| Layer | Choice | Notes |
|-------|--------|-------|
| Language | **Python 3.11+** | Plays to the user's strength |
| Web framework | **FastAPI** | |
| Interactivity | **HTMX** (server-rendered partials) | No JS build step, no SPA. Council: unanimous |
| Templates | **Jinja2** | |
| Styling | **Pico.css** (classless, via CDN) | Beautiful mobile-first defaults, zero build |
| ORM | **SQLModel** (SQLAlchemy 2.x + Pydantic) | DB-agnostic via `DATABASE_URL` |
| DB (prod) | **Neon Postgres** (free tier) | `postgresql+psycopg://...?sslmode=require` |
| DB (local/test) | **SQLite** | Same code path — that's the point |
| Auth | **Google OAuth (OIDC)** via **Authlib** | Allowlist of 4 emails. All 4 confirmed to have Google |
| Sessions | Starlette `SessionMiddleware` (signed cookie) | Needs `itsdangerous` + `SECRET_KEY` |
| Packaging | **uv** | Never pip/poetry directly |
| Lint/format/types | **ruff**, **mypy** (strict) | |
| Tests | **pytest** + FastAPI `TestClient` | |
| Container | **Dockerfile** + `docker-compose.yml` | |
| Host | **Google Cloud Run** | `min-instances=0` (scale to zero, free). Cold start ~1–2s accepted |

**Why DB-agnostic matters:** the user worried hosting was a big lock-in decision. It isn't — because
all DB access goes through `DATABASE_URL` + SQLModel, swapping SQLite↔Postgres↔Turso later is a
config change, not a rewrite. Keep it that way: **never** write raw SQLite- or Postgres-specific SQL.

---

## 1a. Two environments: local dev first, then prod (REQUIRED)

The user wants to run and review the app **on their own machine first**, with **no cloud accounts**,
then deploy to prod only once it looks good. The same code and container serve both — only env vars
differ.

| | Local dev | Production |
|---|---|---|
| DB | SQLite file (`sqlite:///./dev.db`) — auto-created, zero setup | Neon Postgres |
| Auth | `/auth/dev-login` (no Google needed) | Real Google OAuth + allowlist |
| `ENV` | `development` | `production` |
| Run | `uv run uvicorn family_tasks.main:app --reload` **or** `docker compose up` | Cloud Run |
| URL | `http://localhost:8000` | `https://<service>.run.app` |
| Cloud accounts needed | **none** | GCP + Neon + Google OAuth |

**Local dev flow — must work end-to-end with zero cloud setup:**
1. `cp .env.example .env` (defaults already point at SQLite + `ENV=development`).
2. `uv sync`
3. `uv run uvicorn family_tasks.main:app --reload`  (or `docker compose up` to exercise the container)
4. Open `http://localhost:8000` → click **"Continue as Dev (local)"** on the login page (shown only
   when `ENV=development`) → use the full app: add, complete, reactivate, archive, unarchive, delete.

This is a **hard requirement**: the whole app must be usable locally (verified in Phases 4 & 6)
before any deployment. Prod (§14) is a separate, later step, gated on the user's explicit approval —
do not start it as part of the build.

---

## 2. Final repository layout

Follow the workspace `src/` convention. Create exactly this:

```
family-tasks/
├── PLAN.md                      # this file
├── CLAUDE.md                    # project rules (create in Phase 0, content below)
├── pyproject.toml               # uv-managed
├── uv.lock                      # generated by `uv lock` / `uv sync`
├── .env.example                 # template, NEVER a populated .env
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── src/
│   └── family_tasks/
│       ├── __init__.py
│       ├── main.py              # app factory, middleware, router registration, startup
│       ├── config.py            # pydantic-settings, reads env
│       ├── db.py                # engine (sqlite|postgres), session dep, init_db()
│       ├── models.py            # SQLModel: User, Task, TaskStatus
│       ├── auth.py              # Authlib OAuth, /login /auth/* /logout, require_user dep, dev-login
│       ├── tasks.py             # APIRouter: lifecycle routes + HTMX partial rendering
│       ├── humanize.py          # "asked 3 days ago" helper
│       ├── templates/
│       │   ├── base.html
│       │   ├── login.html
│       │   ├── active.html
│       │   ├── done.html
│       │   ├── archive.html
│       │   └── partials/
│       │       ├── task_list.html
│       │       └── task_row.html
│       └── static/
│           └── app.css          # small overrides on top of Pico
└── tests/
    ├── conftest.py
    ├── test_lifecycle.py
    └── test_auth.py
```

> Per workspace rules: **do not** create a README unless asked. Deploy/run instructions live in this
> plan and in `CLAUDE.md`.

---

## 3. Data model (exact)

`src/family_tasks/models.py`:

```python
from datetime import datetime, timezone
from enum import Enum
from sqlmodel import SQLModel, Field


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
    created_by_name: str                      # denormalized for display
    assigned_to_email: str | None = None      # optional; one of the 4, or None
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
    archived_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utcnow)
```

**Lifecycle rules (implement as small pure functions or inline in routes, but obey exactly):**

| Action | Precondition | Effect |
|--------|--------------|--------|
| create | — | `status=active`, `created_by_*` = current user, `created_at=now` |
| complete | status==active | `status=done`, `completed_at=now`, `updated_at=now` |
| reactivate | status==done | `status=active`, `completed_at=None`, `updated_at=now` |
| archive | status in {active, done} | `status=archived`, `archived_at=now`, `updated_at=now` |
| unarchive | status==archived | `status=active`, `archived_at=None`, `completed_at=None`, `updated_at=now` |
| toggle_recurring | any | flip `is_recurring`, `updated_at=now` |
| delete (hard) | status==archived only | row removed permanently |

If a precondition fails, return HTTP 409 with a short message (don't silently no-op).

---

## 4. Config & environment

`.env.example` (commit this; never commit a real `.env`):

```dotenv
# Runtime
ENV=development                      # development | production
BASE_URL=http://localhost:8000       # prod: https://<service>-<hash>.<region>.run.app
SECRET_KEY=change-me-to-a-long-random-string

# Database (DB-agnostic). Local default uses SQLite file.
DATABASE_URL=sqlite:///./dev.db
# Prod (Neon):
# DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require

# Google OAuth (OIDC)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Access control: exactly the family's 4 Google emails, comma-separated, lowercased.
ALLOWED_EMAILS=person1@gmail.com,person2@gmail.com,person3@gmail.com,person4@gmail.com
```

`src/family_tasks/config.py` uses `pydantic-settings`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    base_url: str = "http://localhost:8000"
    secret_key: str = "dev-insecure-secret"
    database_url: str = "sqlite:///./dev.db"
    google_client_id: str = ""
    google_client_secret: str = ""
    allowed_emails: str = ""

    @property
    def allowlist(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_emails.split(",") if e.strip()}

    @property
    def is_prod(self) -> bool:
        return self.env == "production"


settings = Settings()
```

---

## 5. Database engine (the DB-agnostic bit)

`src/family_tasks/db.py`:

```python
from collections.abc import Generator
from sqlmodel import Session, SQLModel, create_engine
from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)


def init_db() -> None:
    # v1 uses create_all (simple, fixed schema). If the schema ever evolves, introduce Alembic then.
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
```

> `pool_pre_ping=True` matters for Neon: its compute auto-suspends after 5 min idle, so the first
> query after a cold start may hit a stale connection. `pool_pre_ping` transparently reconnects.

---

## 6. Auth — Google OAuth + allowlist (the highest-risk part; follow exactly)

`src/family_tasks/auth.py`. Key gotchas baked in below — **read the comments**.

```python
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session
from .config import settings
from .db import get_session
from .models import User

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    client_kwargs={"scope": "openid email profile"},
)

router = APIRouter()


def current_user(request: Request) -> dict | None:
    return request.session.get("user")


def require_user(request: Request) -> dict:
    user = request.session.get("user")
    if not user:
        # Raise 401; main.py has an exception handler that turns 401 on browser GETs into a
        # redirect to /login. HTMX/API callers get a real 401.
        raise HTTPException(status_code=401, detail="login required")
    return user


@router.get("/auth/login")
async def auth_login(request: Request):
    # IMPORTANT: build redirect_uri from BASE_URL, NOT request.url_for(...).
    # Behind Cloud Run's TLS-terminating proxy, url_for() yields http:// and Google rejects the
    # redirect_uri as a mismatch. Constructing from settings.base_url avoids this entirely.
    redirect_uri = settings.base_url.rstrip("/") + "/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback")
async def auth_callback(request: Request, session: Session = Depends(get_session)):
    token = await oauth.google.authorize_access_token(request)
    info = token.get("userinfo")  # Authlib parses the OIDC id_token into 'userinfo'
    if not info or not info.get("email"):
        raise HTTPException(status_code=400, detail="no email from Google")

    email = info["email"].strip().lower()
    if email not in settings.allowlist:
        # This is the access gate. Not in the family allowlist -> blocked.
        raise HTTPException(status_code=403, detail="This app is private to the family.")

    name = info.get("name") or email.split("@")[0]
    picture = info.get("picture")

    db_user = session.get(User, email)
    if db_user is None:
        db_user = User(email=email, display_name=name, picture_url=picture)
    else:
        db_user.display_name, db_user.picture_url = name, picture
    session.add(db_user)
    session.commit()

    request.session["user"] = {"email": email, "name": name, "picture": picture}
    return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# --- DEV ONLY: lets you use the app locally without Google. Guarded by ENV. ---
@router.get("/auth/dev-login")
def dev_login(request: Request):
    if settings.is_prod:
        raise HTTPException(status_code=404)
    request.session["user"] = {
        "email": "dev@example.com", "name": "Dev User", "picture": None,
    }
    return RedirectResponse(url="/", status_code=303)
```

> `/login` (the page with the Google button) is a GET route in `main.py` or `tasks.py` that renders
> `login.html`; it is **not** protected. Everything else task-related is protected by `require_user`.

**Auth acceptance criteria:**
- An email **not** in `ALLOWED_EMAILS` is blocked at `/auth/callback` with 403.
- Hitting any protected page while logged out redirects to `/login`.
- `/auth/dev-login` works only when `ENV != production`; returns 404 in prod.

---

## 7. Routes (exact route table)

All task routes require `require_user`. Mutating endpoints accept a `view` form field
(`active` | `done` | `archive`) and **return the re-rendered `task_list.html` partial for that
view**. This single pattern keeps HTMX dead-simple and robust — no out-of-band swaps.

| Method | Path | Purpose | Returns |
|--------|------|---------|---------|
| GET | `/` | redirect → `/tasks` | 303 |
| GET | `/tasks` | Active list page | `active.html` |
| GET | `/done` | Done list page | `done.html` |
| GET | `/archive` | Archive page | `archive.html` |
| POST | `/tasks` | Create (form: `title`, `assigned_to_email?`, `is_recurring?`) | `task_list` partial (active) |
| POST | `/tasks/{id}/complete` | active→done | `task_list` partial (view) |
| POST | `/tasks/{id}/reactivate` | done→active | `task_list` partial (view) |
| POST | `/tasks/{id}/archive` | →archived | `task_list` partial (view) |
| POST | `/tasks/{id}/unarchive` | archived→active | `task_list` partial (view) |
| POST | `/tasks/{id}/toggle-recurring` | flip flag | `task_list` partial (view) |
| POST | `/tasks/{id}/delete` | hard delete (archived only) | `task_list` partial (archive) |
| GET | `/login` | login page (Google button), unauthenticated | `login.html` |
| GET | `/auth/login` | start OAuth | redirect to Google |
| GET | `/auth/callback` | finish OAuth + allowlist gate | 303 → `/` |
| GET | `/logout` | clear session | 303 → `/login` |
| GET | `/auth/dev-login` | dev-only login | 303 → `/` (404 in prod) |
| GET | `/healthz` | health check (no auth) | `200 {"ok": true}` |

**Helper to standardize partial responses** (in `tasks.py`):

```python
from sqlmodel import select
from .models import Task, TaskStatus

def render_list(request, templates, session, view: str):
    status = {"active": TaskStatus.active, "done": TaskStatus.done,
              "archive": TaskStatus.archived}[view]
    order = Task.created_at.asc() if view == "active" else Task.updated_at.desc()
    tasks = session.exec(select(Task).where(Task.status == status).order_by(order)).all()
    return templates.TemplateResponse(
        "partials/task_list.html",
        {"request": request, "tasks": tasks, "view": view},
    )
```

---

## 8. Frontend — HTMX + Pico, mobile-first

**`base.html`** loads Pico from CDN and HTMX from CDN, sets viewport for mobile, renders a top nav
(Active · Done · Archive) + Logout.

```html
<!doctype html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Family Tasks</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
  <link rel="stylesheet" href="/static/app.css">
  <script src="https://unpkg.com/htmx.org@2.0.4"></script>
</head>
<body>
  <main class="container">
    <nav>
      <ul><li><strong>👨‍👩‍👧‍👦 Family Tasks</strong></li></ul>
      <ul>
        <li><a href="/tasks">Active</a></li>
        <li><a href="/done">Done</a></li>
        <li><a href="/archive">Archive</a></li>
        {% if user %}<li><a href="/logout" role="button" class="secondary outline">Logout</a></li>{% endif %}
      </ul>
    </nav>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

> Every GET page handler passes `user=current_user(request)` into the template context so the nav
> can render Logout.

**`active.html`** — add-task form (single text input + big submit) then the list partial:

```html
{% extends "base.html" %}
{% block content %}
<form hx-post="/tasks" hx-target="#task-list" hx-swap="outerHTML" hx-on::after-request="this.reset()">
  <fieldset role="group">
    <input name="title" placeholder="What needs doing?" required autocomplete="off">
    <button type="submit">Add</button>
  </fieldset>
  <input type="hidden" name="view" value="active">
</form>
{% include "partials/task_list.html" %}
{% endblock %}
```

`done.html` and `archive.html` are the same shape minus the add-form (just `{% include "partials/task_list.html" %}`
with the right `view` in context).

**`partials/task_list.html`** — wraps rows in `#task-list`; optional 30s poll (see note):

```html
<div id="task-list">
  {% if not tasks %}<p><em>Nothing here. 🎉</em></p>{% endif %}
  {% for task in tasks %}{% include "partials/task_row.html" %}{% endfor %}
</div>
```

> **Optional** live-refresh: to let other family members' changes appear without manual reload, add
> `hx-get="/tasks/list?view={{ view }}" hx-trigger="every 30s" hx-swap="outerHTML"` to the
> `#task-list` div **and** add a `GET /tasks/list` route returning this partial. Implement only if
> time allows; not required for acceptance.

**`partials/task_row.html`** — one task, buttons appropriate to its `view`. Every action button uses
`hx-target="#task-list" hx-swap="outerHTML"` and includes the `view` (via `hx-vals` or a hidden
field). Show attribution (`created_by_name`), humanized age (`humanize.py`), a recurring badge, and
assignee if set. Buttons by view:
- **active:** ✓ Complete · 🔁 recurring toggle · 📦 Archive
- **done:** ↩ Reactivate · 📦 Archive
- **archive:** ↩ Unarchive · 🗑 Delete (`hx-confirm="Delete permanently?"`)

Example button:

```html
<button hx-post="/tasks/{{ task.id }}/complete" hx-vals='{"view": "{{ view }}"}'
        hx-target="#task-list" hx-swap="outerHTML">✓</button>
```

**`app.css`** — keep tiny: big tap targets (min 44px), single column, subtle fade/strike on complete.

**`login.html`** — centered card, one button `<a href="/auth/login" role="button">Sign in with Google</a>`
plus: "Private to our family — only approved accounts can enter." When `ENV=development`, also render
a `<a href="/auth/dev-login" role="button" class="secondary">Continue as Dev (local)</a>` so local
testing is one click and never depends on Google. The `GET /login` handler passes
`is_dev=not settings.is_prod` into the template context to gate that button.

---

## 9. `main.py` wiring

```python
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from .config import settings
from .db import init_db
from . import auth, tasks

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, https_only=settings.is_prod)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
app.state.templates = templates  # routers read request.app.state.templates
app.include_router(auth.router)
app.include_router(tasks.router)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.exception_handler(StarletteHTTPException)
async def auth_redirect(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401 and request.method == "GET" and "text/html" in request.headers.get("accept", ""):
        return RedirectResponse(url="/login", status_code=303)
    raise exc
```

> Use **one** `Jinja2Templates` instance (the one on `app.state.templates`). Routers fetch it via
> `request.app.state.templates`. Do not create a second instance inside `tasks.py`/`auth.py`.

---

## 10. Dependencies (`pyproject.toml`)

```toml
[project]
name = "family-tasks"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "jinja2>=3.1",
    "sqlmodel>=0.0.22",
    "psycopg[binary]>=3.2",
    "authlib>=1.3",
    "httpx>=0.27",
    "itsdangerous>=2.2",
    "python-multipart>=0.0.9",
    "pydantic-settings>=2.4",
]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "mypy>=1.11"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
strict = true
ignore_missing_imports = true

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/family_tasks"]
```

Manage with: `uv sync` (creates `.venv` + `uv.lock`). Run: `uv run uvicorn family_tasks.main:app --reload`.

---

## 11. Containerization

**`Dockerfile`** (uv-based; listens on Cloud Run's `$PORT`):

```dockerfile
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
# Cloud Run injects PORT (default 8080). Must bind 0.0.0.0.
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn family_tasks.main:app --host 0.0.0.0 --port ${PORT}"]
```

**`.dockerignore`**: `.venv`, `__pycache__`, `*.db`, `.env`, `.git`, `tests`, `.pytest_cache`.

**`docker-compose.yml`** (local convenience — app on SQLite by default):

```yaml
services:
  app:
    build: .
    ports: ["8000:8080"]
    env_file: .env
    environment:
      - PORT=8080
    volumes:
      - ./dev.db:/app/dev.db   # persist local SQLite across restarts
```

---

## 12. Tests (`tests/`)

Use SQLite in-memory + a `get_session` dependency override. **Do not call Google in tests** — log in
via the dev-login route (`ENV=development`) or seed `request.session` directly. Keep the allowlist
check unit-testable without OAuth.

`test_lifecycle.py` must cover:
- create → in active query, not in done/archive
- complete → leaves active, in done, `completed_at` set
- reactivate → leaves done, back in active, `completed_at` cleared
- archive (from active and from done) → in archive
- unarchive → back to active
- toggle_recurring → flag flips
- delete on archived → row gone; delete on non-archived → 409
- each lifecycle endpoint returns the `task_list` partial (200, contains expected task)

`test_auth.py` must cover:
- allowlisted email → session set, redirect to `/`
- non-allowlisted email → 403, no session
- protected GET while logged out → 303 redirect to `/login`
- `/auth/dev-login` → 404 when `ENV=production`

Meaningful coverage of lifecycle + auth gate. Don't chase 100%.

---

## 13. Implementation order (phases — do in sequence, verify each)

- [ ] **Phase 0 — Scaffold.** Create the tree in §2. `git init`. Write `pyproject.toml`, `.gitignore`
      (`.venv/`, `.env`, `*.db`, `__pycache__/`, `*.egg-info`, `.pytest_cache/`), `.dockerignore`,
      `.env.example`, project `CLAUDE.md` (§16). `uv sync`. Commit `chore: scaffold family-tasks`.
- [ ] **Phase 1 — Config + DB + models.** `config.py`, `db.py`, `models.py`. Verify `init_db()`
      creates tables against SQLite. Commit `feat: data model and db engine`.
- [ ] **Phase 2 — Auth.** `auth.py` + `main.py` middleware + `login.html` + dev-login. Verify
      `/auth/dev-login` logs you in locally and the allowlist rejects unknown emails (unit test).
      Commit `feat: google oauth with family allowlist`.
- [ ] **Phase 3 — Task routes + lifecycle.** `tasks.py` (all §7 routes), `render_list`, `humanize.py`.
      Commit `feat: task lifecycle routes`.
- [ ] **Phase 4 — Templates + HTMX + styling.** All templates + `app.css`. Verify in a browser that
      add / complete / reactivate / archive / unarchive / delete all work via HTMX with no full
      reloads, and the layout is clean on a narrow (mobile) viewport. Commit `feat: htmx ui`.
- [ ] **Phase 5 — Tests.** `conftest.py` + the two test files. `uv run pytest` green. Commit
      `test: lifecycle and auth coverage`.
- [ ] **Phase 6 — Container + local verify.** `Dockerfile`, `docker-compose.yml`. `docker compose up`,
      confirm it serves on `http://localhost:8000`, dev-login + lifecycle work. Commit `chore: containerize`.
- [ ] **Phase 7 — Quality gate.**
      `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest` — all
      clean. Commit `chore: lint, types, tests green`.

**Stop after Phase 7 and report to the user.** Deployment (§14) needs the user's Google/GCP/Neon
console actions and secrets — present it as instructions; do not run it autonomously, and **never**
push to a remote without explicit instruction.

---

## 14. Deployment runbook (for the USER — document, don't auto-run)

One-time console steps the user performs. Mirror these into `CLAUDE.md`.

1. **Neon:** create a free project → copy the connection string → make it
   `postgresql+psycopg://...?sslmode=require`. That's prod `DATABASE_URL`.
2. **GCP project:** create one; enable **Cloud Run** and **Cloud Build** APIs.
3. **OAuth consent screen:** User type **External**; fill app name/support email. **Leave it in
   "Testing" mode** and add the 4 family emails as **Test users** — Testing mode allows up to 100 test
   users with **no Google app-verification review**. (Publishing would trigger verification; we don't
   need it for 4 people.)
4. **OAuth client ID:** type **Web application**. Authorized redirect URI =
   `https://<cloud-run-url>/auth/callback`. Chicken-and-egg: deploy once to learn the URL, then add
   the redirect URI and set `BASE_URL` to that URL. Copy Client ID + Secret.
5. **Deploy:** `gcloud run deploy family-tasks --source . --region <region> --allow-unauthenticated --min-instances=0`.
   `--allow-unauthenticated` is correct — *our app* does the auth (Google + allowlist); this flag only
   means Cloud Run won't block the request before our code runs.
6. **Env / secrets** on the service: `ENV=production`, `BASE_URL`, `SECRET_KEY` (long random),
   `DATABASE_URL` (Neon), `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ALLOWED_EMAILS`. Prefer
   **Secret Manager** for the secret-bearing ones.
7. Visit the URL → "Sign in with Google" → confirm a family email gets in and a random Gmail is
   rejected with 403.

**Free-tier guardrails:** `min-instances=0` keeps it free (accept ~1–2s cold start). Neon suspends
after 5 min idle, resumes <1s (`pool_pre_ping` handles reconnect). Data is kilobytes — far under the
0.5 GB / 2M-request limits.

---

## 15. Out of scope for v1 (do NOT build unless the user asks)

Automatic recurring schedules (cron), due dates, reminders/push notifications, comments, file
attachments, multiple lists/households, websockets, an admin panel, PWA/offline. The 30s poll (§8)
is the *only* optional extra, and only if time allows.

---

## 16. Project `CLAUDE.md` to create in Phase 0

```markdown
# family-tasks

Private shared to-do app for a family of 4. FastAPI + HTMX (server-rendered), SQLModel over a
DB-agnostic `DATABASE_URL` (SQLite local, Neon Postgres prod), Google OAuth restricted to a
4-email allowlist. Containerized for Google Cloud Run (free tier). Mobile-first.

## Lifecycle
Active → (complete) → Done → (reactivate) → Active. Any task → (archive) → Archived → (unarchive) → Active.
"Done" = removed from the active list but retained. "Archived" = permanent storage.

## Rules
- uv only (never pip/poetry directly). Run: `uv run uvicorn family_tasks.main:app --reload`.
- Keep DB access DB-agnostic — never write SQLite- or Postgres-specific SQL.
- Auth is the email allowlist in `ALLOWED_EMAILS`; the access gate lives in `auth.py:auth_callback`.
- ruff + mypy (strict) + pytest must stay green. Conventional Commits.
- Never commit `.env` or `*.db`. Never push to remote without explicit instruction.

## Run locally without Google
Set `ENV=development` and visit `/auth/dev-login`.

## Deploy
See PLAN.md §14 (Cloud Run + Neon + OAuth runbook).
```

---

*End of plan. Implement phases 0→7 in order, verify each checkpoint, keep the quality gate green,
then hand back to the user for the deployment steps.*
