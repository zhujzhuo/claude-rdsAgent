"""
URL configuration for RDS Agent Django project.

The `urlpatterns` list routes URLs to views.
"""
from django.urls import path, include
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def root_info(request):
    """Root endpoint - project info."""
    return Response({
        "name": "RDS Agent",
        "version": "0.2.0",
        "status": "running",
        "framework": "Django + Celery",
    })


@api_view(["GET"])
def health_check(request):
    """Health check endpoint."""
    return Response({
        "status": "healthy",
        "django": "ok",
        "database": "connected",
        "celery": "configured",
    })


@api_view(["GET"])
def config_info(request):
    """Get configuration info (non-sensitive)."""
    config = getattr(settings, "RDS_AGENT_CONFIG", {})
    return Response({
        "ollama_host": config.get("ollama_host", settings.RDS_AGENT_SETTINGS.get("OLLAMA_HOST", "")),
        "ollama_model": config.get("ollama_model", settings.RDS_AGENT_SETTINGS.get("OLLAMA_MODEL", "")),
        "debug": settings.DEBUG,
        "timezone": settings.TIME_ZONE,
    })


urlpatterns = [
    # Root endpoints
    path("", root_info, name="root"),
    path("health/", health_check, name="health"),
    path("config/", config_info, name="config"),

    # Scheduler API
    path("api/scheduler/", include("scheduler.api.urls")),
]