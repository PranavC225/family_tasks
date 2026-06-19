from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import auth, tasks
from .auth import current_user
from .config import settings
from .db import init_db

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


@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "user": current_user(request), "is_dev": not settings.is_prod},
    )


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.exception_handler(StarletteHTTPException)
async def auth_redirect(request: Request, exc: StarletteHTTPException):
    if (
        exc.status_code == 401
        and request.method == "GET"
        and "text/html" in request.headers.get("accept", "")
    ):
        return RedirectResponse(url="/login", status_code=303)
    raise exc
