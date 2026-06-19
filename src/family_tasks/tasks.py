from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from .auth import current_user, require_user
from .db import get_session
from .humanize import time_ago
from .models import Task, TaskStatus, utcnow

router = APIRouter()

_STATUS_BY_VIEW = {
    "active": TaskStatus.active,
    "done": TaskStatus.done,
    "archive": TaskStatus.archived,
}


def _tasks_for_view(session: Session, view: str) -> list[Task]:
    status = _STATUS_BY_VIEW[view]
    order = Task.created_at.asc() if view == "active" else Task.updated_at.desc()
    return list(session.exec(select(Task).where(Task.status == status).order_by(order)).all())


def render_list(request: Request, session: Session, view: str):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "partials/task_list.html",
        {"tasks": _tasks_for_view(session, view), "view": view, "time_ago": time_ago},
    )


def render_page(request: Request, session: Session, view: str, template: str):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        template,
        {
            "tasks": _tasks_for_view(session, view),
            "view": view,
            "user": current_user(request),
            "time_ago": time_ago,
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
    user: dict = Depends(require_user),
    session: Session = Depends(get_session),
):
    return render_page(request, session, "active", "active.html")


@router.get("/done")
def done_page(
    request: Request,
    user: dict = Depends(require_user),
    session: Session = Depends(get_session),
):
    return render_page(request, session, "done", "done.html")


@router.get("/archive")
def archive_page(
    request: Request,
    user: dict = Depends(require_user),
    session: Session = Depends(get_session),
):
    return render_page(request, session, "archive", "archive.html")


@router.post("/tasks")
def create_task(
    request: Request,
    title: str = Form(...),
    assigned_to_email: str | None = Form(None),
    is_recurring: bool = Form(False),
    user: dict = Depends(require_user),
    session: Session = Depends(get_session),
):
    task = Task(
        title=title.strip(),
        is_recurring=is_recurring,
        created_by_email=user["email"],
        created_by_name=user["name"],
        assigned_to_email=assigned_to_email.strip() if assigned_to_email else None,
    )
    session.add(task)
    session.commit()
    return render_list(request, session, "active")


@router.post("/tasks/{task_id}/complete")
def complete_task(
    request: Request,
    task_id: int,
    view: str = Form(...),
    user: dict = Depends(require_user),
    session: Session = Depends(get_session),
):
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
    user: dict = Depends(require_user),
    session: Session = Depends(get_session),
):
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
    user: dict = Depends(require_user),
    session: Session = Depends(get_session),
):
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
    user: dict = Depends(require_user),
    session: Session = Depends(get_session),
):
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
    user: dict = Depends(require_user),
    session: Session = Depends(get_session),
):
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
    user: dict = Depends(require_user),
    session: Session = Depends(get_session),
):
    task = _get_task_or_404(session, task_id)
    if task.status == TaskStatus.archived:
        session.delete(task)
        session.commit()
    return render_list(request, session, view)
