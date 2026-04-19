"""Integration test configuration."""

import pytest
import os
import sys

# Add project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rds_agent.django_project.settings")


@pytest.fixture(scope="session")
def django_db_setup():
    """Configure Django database for integration tests."""
    from django.conf import settings

    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }


@pytest.fixture(scope="session")
def django_configure():
    """Configure Django for test session."""
    import django
    django.setup()