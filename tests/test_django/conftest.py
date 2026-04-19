"""Django test configuration."""

import pytest
import os
import sys

# Add project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Set Django settings before importing Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rds_agent.django_project.settings")
os.environ.setdefault("DJANGO_DEBUG", "True")


@pytest.fixture(scope="session")
def django_db_setup():
    """Configure Django database for tests."""
    from django.conf import settings

    # Use SQLite for tests (in-memory)
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }


@pytest.fixture(scope="session")
def django_configure():
    """Configure Django for test session."""
    import django
    django.setup()


@pytest.fixture
def task_factory(django_db_setup, django_configure):
    """Factory for creating InspectionTask instances."""
    from scheduler.models.task import InspectionTask

    def create_task(**kwargs):
        defaults = {
            "name": "Test Task",
            "description": "Test task description",
            "target_instances": ["db-test-01"],
            "task_type": "full_inspection",
            "schedule_type": "interval",
            "interval_seconds": 3600,
        }
        defaults.update(kwargs)
        return InspectionTask.objects.create(**defaults)

    return create_task


@pytest.fixture
def alert_rule_factory(django_db_setup, django_configure):
    """Factory for creating AlertRule instances."""
    from scheduler.models.alert import AlertRule

    def create_rule(**kwargs):
        defaults = {
            "name": "Test Rule",
            "description": "Test alert rule",
            "metric_name": "overall_score",
            "operator": "<",
            "threshold": 60,
            "level": "critical",
        }
        defaults.update(kwargs)
        return AlertRule.objects.create(**defaults)

    return create_rule


@pytest.fixture
def notification_channel_factory(django_db_setup, django_configure):
    """Factory for creating NotificationChannel instances."""
    from scheduler.models.notification import NotificationChannel

    def create_channel(**kwargs):
        defaults = {
            "name": "Test Channel",
            "type": "dingtalk",
            "config": {"webhook": "https://oapi.dingtalk.com/robot/send?access_token=test"},
        }
        defaults.update(kwargs)
        return NotificationChannel.objects.create(**defaults)

    return create_channel


@pytest.fixture
def mock_diagnostic_agent():
    """Mock DiagnosticAgent for testing."""
    from unittest.mock import Mock, patch

    mock_result = Mock()
    mock_result.overall_score = 85
    mock_result.overall_status = Mock(value="healthy")
    mock_result.critical_issues = []
    mock_result.warnings = []
    mock_result.suggestions = ["No issues found"]

    with patch("scheduler.tasks.inspection.get_diagnostic_agent") as mock:
        mock_agent = Mock()
        mock_agent.run.return_value = mock_result
        mock.return_value = mock_agent
        yield mock


@pytest.fixture
def mock_report_generator():
    """Mock ReportGenerator for testing."""
    from unittest.mock import Mock, patch
    from pathlib import Path

    with patch("scheduler.tasks.inspection.get_report_generator") as mock:
        mock_generator = Mock()
        mock_generator.save_report.return_value = Path("/tmp/test_report.json")
        mock.return_value = mock_generator
        yield mock


@pytest.fixture
def mock_platform_client():
    """Mock InstancePlatformClient for testing."""
    from unittest.mock import Mock, patch

    mock_instance = Mock()
    mock_instance.id = "test-instance-001"
    mock_instance.name = "db-test-01"
    mock_instance.host = "localhost"
    mock_instance.port = 3306

    with patch("rds_agent.data.instance_platform.get_platform_client") as mock:
        mock_client = Mock()
        mock_client.list_instances.return_value = [mock_instance]
        mock_client.search_instance_by_name.return_value = mock_instance
        mock_client.get_instance_connection.return_value = Mock(
            host="localhost",
            port=3306,
            user="root",
            password="test",
            database="mysql"
        )
        mock.return_value = mock_client
        yield mock