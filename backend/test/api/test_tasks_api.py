from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from blank.db.models import Task
from test.factories import TaskFactory


class TestTasksAPI:
    """Core API behavior tests for tasks endpoints."""

    def test_create_task(self, client: TestClient, db_session: Session):
        """Test creating a task."""
        task_data = {"title": "Test Task", "description": "Test description"}

        response = client.post("/tasks", json=task_data)

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == task_data["title"]
        assert data["completed"] is False
        assert "id" in data

        # Verify persisted to database
        task = db_session.get(Task, data["id"])
        assert task.title == task_data["title"]

    def test_list_tasks_with_filtering(self, client: TestClient, db_session: Session):
        """Test listing and filtering tasks."""
        # Create mix of tasks
        completed_task = TaskFactory.build(completed=True, title="Done task")
        pending_task = TaskFactory.build(completed=False, title="Todo task")

        db_session.add_all([completed_task, pending_task])
        db_session.commit()

        # Test basic listing
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2

        # Test filtering works
        response = client.get("/tasks?completed=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["completed"] is True

    def test_task_crud_workflow(self, client: TestClient, db_session: Session):
        """Test complete CRUD workflow for a task."""
        # Create
        task_data = {"title": "Workflow Task"}
        response = client.post("/tasks", json=task_data)
        assert response.status_code == 200
        task_id = response.json()["id"]

        # Read
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["title"] == task_data["title"]

        # Update
        update_data = {"completed": True}
        response = client.patch(f"/tasks/{task_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["completed"] is True

        # Delete
        response = client.delete(f"/tasks/{task_id}")
        assert response.status_code == 204

        # Verify deleted
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 404

    def test_task_not_found_handling(self, client: TestClient):
        """Test 404 handling for non-existent tasks."""
        response = client.get("/tasks/99999")
        assert response.status_code == 404

        response = client.patch("/tasks/99999", json={"title": "Updated"})
        assert response.status_code == 404

        response = client.delete("/tasks/99999")
        assert response.status_code == 404
