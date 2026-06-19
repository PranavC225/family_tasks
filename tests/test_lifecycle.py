import re

from fastapi.testclient import TestClient


def _extract_task_id(html: str) -> int:
    match = re.search(r"/tasks/(\d+)/complete", html)
    assert match
    return int(match.group(1))


def test_create_appears_only_in_active(logged_in_client: TestClient) -> None:
    r = logged_in_client.post("/tasks", data={"title": "Water plants", "view": "active"})
    assert r.status_code == 200
    assert "Water plants" in r.text
    assert "Water plants" not in logged_in_client.get("/done").text
    assert "Water plants" not in logged_in_client.get("/archive").text


def test_complete_moves_active_to_done(logged_in_client: TestClient) -> None:
    r = logged_in_client.post("/tasks", data={"title": "Wash car", "view": "active"})
    task_id = _extract_task_id(r.text)

    r = logged_in_client.post(f"/tasks/{task_id}/complete", data={"view": "active"})

    assert r.status_code == 200
    assert "Wash car" not in r.text
    assert "Wash car" in logged_in_client.get("/done").text


def test_reactivate_clears_completed_and_returns_to_active(logged_in_client: TestClient) -> None:
    r = logged_in_client.post("/tasks", data={"title": "Mow lawn", "view": "active"})
    task_id = _extract_task_id(r.text)
    logged_in_client.post(f"/tasks/{task_id}/complete", data={"view": "active"})

    r = logged_in_client.post(f"/tasks/{task_id}/reactivate", data={"view": "done"})

    assert r.status_code == 200
    assert "Mow lawn" not in r.text
    assert "Mow lawn" in logged_in_client.get("/tasks").text


def test_archive_from_active_and_from_done(logged_in_client: TestClient) -> None:
    r = logged_in_client.post("/tasks", data={"title": "Pay bills", "view": "active"})
    task_id = _extract_task_id(r.text)

    r = logged_in_client.post(f"/tasks/{task_id}/archive", data={"view": "active"})
    assert "Pay bills" not in r.text
    assert "Pay bills" in logged_in_client.get("/archive").text

    logged_in_client.post(f"/tasks/{task_id}/unarchive", data={"view": "archive"})
    logged_in_client.post(f"/tasks/{task_id}/complete", data={"view": "active"})
    r = logged_in_client.post(f"/tasks/{task_id}/archive", data={"view": "done"})
    assert "Pay bills" not in r.text
    assert "Pay bills" in logged_in_client.get("/archive").text


def test_unarchive_returns_to_active(logged_in_client: TestClient) -> None:
    r = logged_in_client.post("/tasks", data={"title": "Renew passport", "view": "active"})
    task_id = _extract_task_id(r.text)
    logged_in_client.post(f"/tasks/{task_id}/archive", data={"view": "active"})

    r = logged_in_client.post(f"/tasks/{task_id}/unarchive", data={"view": "archive"})

    assert "Renew passport" not in r.text
    assert "Renew passport" in logged_in_client.get("/tasks").text


def test_toggle_recurring_flips_flag(logged_in_client: TestClient) -> None:
    r = logged_in_client.post("/tasks", data={"title": "Take out recycling", "view": "active"})
    task_id = _extract_task_id(r.text)
    assert 'title="Recurring"' not in r.text

    r = logged_in_client.post(f"/tasks/{task_id}/toggle-recurring", data={"view": "active"})
    assert 'title="Recurring"' in r.text

    r = logged_in_client.post(f"/tasks/{task_id}/toggle-recurring", data={"view": "active"})
    assert 'title="Recurring"' not in r.text


def test_delete_archived_removes_row(logged_in_client: TestClient) -> None:
    r = logged_in_client.post("/tasks", data={"title": "Old task", "view": "active"})
    task_id = _extract_task_id(r.text)
    logged_in_client.post(f"/tasks/{task_id}/archive", data={"view": "active"})

    r = logged_in_client.post(f"/tasks/{task_id}/delete", data={"view": "archive"})

    assert r.status_code == 200
    assert "Old task" not in r.text


def test_delete_non_archived_rejected(logged_in_client: TestClient) -> None:
    r = logged_in_client.post("/tasks", data={"title": "Still active", "view": "active"})
    task_id = _extract_task_id(r.text)

    r = logged_in_client.post(f"/tasks/{task_id}/delete", data={"view": "active"})

    assert r.status_code == 409
    assert logged_in_client.get("/tasks").text.count("Still active") == 1
