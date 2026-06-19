from typing import TypedDict

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
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


class AuthUser(TypedDict):
    email: str
    name: str
    picture: str | None


def current_user(request: Request) -> AuthUser | None:
    return request.session.get("user")


def require_user(request: Request) -> AuthUser:
    user = current_user(request)
    if not user:
        # Raise 401; main.py has an exception handler that turns 401 on browser GETs into a
        # redirect to /login. HTMX/API callers get a real 401.
        raise HTTPException(status_code=401, detail="login required")
    return user


@router.get("/auth/login")
async def auth_login(request: Request) -> Response:
    # IMPORTANT: build redirect_uri from BASE_URL, NOT request.url_for(...).
    # Behind Cloud Run's TLS-terminating proxy, url_for() yields http:// and Google rejects the
    # redirect_uri as a mismatch. Constructing from settings.base_url avoids this entirely.
    redirect_uri = settings.base_url.rstrip("/") + "/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)  # type: ignore[no-any-return]


@router.get("/auth/callback")
async def auth_callback(request: Request, session: Session = Depends(get_session)) -> Response:
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
def logout(request: Request) -> Response:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# --- DEV ONLY: lets you use the app locally without Google. Guarded by ENV. ---
@router.get("/auth/dev-login")
def dev_login(request: Request) -> Response:
    if settings.is_prod:
        raise HTTPException(status_code=404)
    request.session["user"] = {
        "email": "dev@example.com",
        "name": "Dev User",
        "picture": None,
    }
    return RedirectResponse(url="/", status_code=303)
