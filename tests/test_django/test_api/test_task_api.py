"""Tests for InspectionTask API endpoints."""

import pytest
from rest_framework.test import APIClient
from rest_framework import status


pytestmark = pytest.mark.django_db


class TestInspectionTaskAPI:
    """Test cases for InspectionTask API endpoints."""

    def test_list_tasks_empty(self):
        """Test listing tasks when empty."""
        client = APIClient()
        response = client.get("/api/scheduler/tasks/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0
        assert response.data["results"] == []

    def test_list_tasks(self, task_factory):
        """Test listing tasks."""
        task_factory(name="Task 1")
        task_factory(name="Task 2")
        task_factory(name="Task 3")

        client = APIClient()
        response = client.get("/api/scheduler/tasks/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 3

    def test_create_task(self):
        """Test creating a new task."""
        client = APIClient()
        data = {
            "name": "New Task",
            "description": "Test task",
            "target_instances": ["db-01"],
            "task_type": "full_inspection",
            "schedule_type": "interval",
            "interval_seconds": 3600,
        }

        response = client.post("/api/scheduler/tasks/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Task"
        assert response.data["status"] == "enabled"

    def test_create_cron_task(self):
        """Test creating a cron task."""
        client = APIClient()
        data = {
            "name": "Cron Task",
            "description": "Daily check",
            "target_instances": ["db-01"],
            "task_type": "quick_check",
            "schedule_type": "cron",
            "cron_expression": "0 9 * * *",
        }

        response = client.post("/api/scheduler/tasks/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["schedule_type"] == "cron"
        assert response.data["cron_expression"] == "0 9 * * *"

    def test_retrieve_task(self, task_factory):
        """Test retrieving a single task."""
        task = task_factory(name="Detail Task")

        client = APIClient()
        response = client.get(f"/api/scheduler/tasks/{task.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Detail Task"

    def test_update_task(self, task_factory):
        """Test updating a task."""
        task = task_factory(name="Original Name")

        client = APIClient()
        data = {"name": "Updated Name"}
        response = client.patch(f"/api/scheduler/tasks/{task.id}/", data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Name"

    def test_delete_task(self, task_factory):
        """Test deleting a task."""
        task = task_factory(name="Delete Task")

        client = APIClient()
        response = client.delete(f"/api/scheduler/tasks/{task.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify task is deleted
        from scheduler.models.task import InspectionTask
        assert not InspectionTask.objects.filter(id=task.id).exists()

    def test_enable_task_action(self, task_factory):
        """Test enable action on task."""
        from scheduler.models.task import TaskStatus

        task = task_factory(name="Test Task", status=TaskStatus.DISABLED)

        client = APIClient()
        response = client.post(f"/api/scheduler/tasks/{task.id}/enable/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.ENABLED

    def test_disable_task_action(self, task_factory):
        """Test disable action on task."""
        from scheduler.models.task import TaskStatus

        task = task_factory(name="Test Task", status=TaskStatus.ENABLED)

        client = APIClient()
        response = client.post(f"/api/scheduler/tasks/{task.id}/disable/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.DISABLED

    def test_run_task_action(self, task_factory):
        """Test run action on task."""
        task = task_factory(name="Test Task")

        client = APIClient()
        response = client.post(f"/api/scheduler/tasks/{task.id}/run/")

        assert response.status_code == status.HTTP_200_OK
        assert "celery_task_id" in response.data
        assert response.data["status"] == "triggered"

    def test_filter_tasks_by_status(self, task_factory):
        """Test filtering tasks by status."""
        from scheduler.models.task import TaskStatus

        task_factory(name="Enabled 1", status=TaskStatus.ENABLED)
        task_factory(name="Enabled 2", status=TaskStatus.ENABLED)
        task_factory(name="Disabled", status=TaskStatus.DISABLED)

        client = APIClient()
        response = client.get("/api/scheduler/tasks/?status=enabled")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_filter_tasks_by_type(self, task_factory):
        """Test filtering tasks by type."""
        task_factory(name="Full", task_type="full_inspection")
        task_factory(name="Quick", task_type="quick_check")
        task_factory(name="Another Full", task_type="full_inspection")

        client = APIClient()
        response = client.get("/api/scheduler/tasks/?task_type=full_inspection")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_search_tasks_by_name(self, task_factory):
        """Test searching tasks by name."""
        task_factory(name="Production Check")
        task_factory(name="Development Check")
        task_factory(name="Staging Monitor")

        client = APIClient()
        response = client.get("/api/scheduler/tasks/?search=Check")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_order_tasks(self, task_factory):
        """Test ordering tasks."""
        task_factory(name="Alpha")
        task_factory(name="Beta")
        task_factory(name="Gamma")

        client = APIClient()
        response = client.get("/api/scheduler/tasks/?ordering=name")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0]["name"] == "Alpha"

        response_desc = client.get("/api/scheduler/tasks/?ordering=-name")
        assert response_desc.data["results"][0]["name"] == "Gamma"