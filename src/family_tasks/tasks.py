from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, col, select

from .auth import AuthUser, current_user, require_user
from .config import settings
from .db import get_session
from .humanize import time_ago
from .models import Task, TaskStatus, User, utcnow
from .push import notify

router = APIRouter()

_STATUS_BY_VIEW = {
    "active": TaskStatus.active,
    "done": TaskStatus.done,
    "archive": TaskStatus.archived,
}


def recipients_for(creator: str, assignee: str | None, allowlist: set[str]) -> list[str]:
    if assignee:
        return [assignee] if assignee != creator else []
    return sorted(e for e in allowlist if e != creator)


def _tasks_for_view(session: Session, view: str) -> list[Task]:
    status = _STATUS_BY_VIEW[view]
    order = col(Task.created_at).asc() if view == "active" else col(Task.updated_at).desc()
    return list(session.exec(select(Task).where(Task.status == status).order_by(order)).all())


def render_list(request: Request, session: Session, view: str) -> Response:
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "partials/task_list.html",
        {"tasks": _tasks_for_view(session, view), "view": view, "time_ago": time_ago},
    )


def render_page(request: Request, session: Session, view: str, template: str) -> Response:
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        template,
        {
            "tasks": _tasks_for_view(session, view),
            "view": view,
            "user": current_user(request),
            "time_ago": time_ago,
            "users": list(session.exec(select(User)).all()),
        },
    )


def _get_task_or_404(session: Session, task_id: int) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/tasks", status_code=303)


@router.get("/tasks")
def tasks_page(
    request: Request,
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    return render_page(request, session, "active", "active.html")


@router.get("/done")
def done_page(
    request: Request,
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    return render_page(request, session, "done", "done.html")


@router.get("/archive")
def archive_page(
    request: Request,
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    return render_page(request, session, "archive", "archive.html")


@router.post("/tasks")
def create_task(
    request: Request,
    background: BackgroundTasks,
    title: str = Form(...),
    assigned_to_email: str | None = Form(None),
    is_recurring: bool = Form(False),
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    assignee = assigned_to_email.strip().lower() if assigned_to_email else None
    task = Task(
        title=title.strip(),
        is_recurring=is_recurring,
        created_by_email=user["email"],
        created_by_name=user["name"],
        assigned_to_email=assignee,
    )
    session.add(task)
    session.commit()

    targets = recipients_for(user["email"], assignee, settings.allowlist)
    if targets:
        label = "New task assigned to you" if assignee else "New family task"
        background.add_task(notify, targets, label, f"{user['name']}: {task.title}")

    return render_list(request, session, "active")


@router.post("/tasks/{task_id}/complete")
def complete_task(
    request: Request,
    task_id: int,
    view: str = Form(...),
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    task = _get_task_or_404(session, task_id)
    task.status = TaskStatus.done
    task.completed_at = task.updated_at = utcnow()
    session.add(task)
    session.commit()
    return render_list(request, session, view)


@router.post("/tasks/{task_id}/reactivate")
def reactivate_task(
    request: Request,
    task_id: int,
    view: str = Form(...),
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    task = _get_task_or_404(session, task_id)
    task.status = TaskStatus.active
    task.completed_at = None
    task.updated_at = utcnow()
    session.add(task)
    session.commit()
    return render_list(request, session, view)


@router.post("/tasks/{task_id}/archive")
def archive_task(
    request: Request,
    task_id: int,
    view: str = Form(...),
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    task = _get_task_or_404(session, task_id)
    task.status = TaskStatus.archived
    task.archived_at = task.updated_at = utcnow()
    session.add(task)
    session.commit()
    return render_list(request, session, view)


@router.post("/tasks/{task_id}/unarchive")
def unarchive_task(
    request: Request,
    task_id: int,
    view: str = Form(...),
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    task = _get_task_or_404(session, task_id)
    task.status = TaskStatus.active
    task.archived_at = None
    task.updated_at = utcnow()
    session.add(task)
    session.commit()
    return render_list(request, session, view)


@router.post("/tasks/{task_id}/toggle-recurring")
def toggle_recurring(
    request: Request,
    task_id: int,
    view: str = Form(...),
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    task = _get_task_or_404(session, task_id)
    task.is_recurring = not task.is_recurring
    task.updated_at = utcnow()
    session.add(task)
    session.commit()
    return render_list(request, session, view)


@router.post("/tasks/{task_id}/delete")
def delete_task(
    request: Request,
    task_id: int,
    view: str = Form(...),
    user: AuthUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    task = _get_task_or_404(session, task_id)
    if task.status != TaskStatus.archived:
        raise HTTPException(status_code=409, detail="only archived tasks can be deleted")
    session.delete(task)
    session.commit()
    return render_list(request, session, view)
