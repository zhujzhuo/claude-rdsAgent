# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RDS Agent is a MySQL database intelligent Q&A and O&M assistant (MySQL数据库智能运维助手). It uses a multi-agent architecture with Django + Celery for web/tasks and multiple LLM agent frameworks for different query complexity levels. The project is written in Chinese (comments, docs, prompts).

## Development Commands

```bash
# Install dependencies (uses uv)
uv sync

# Run tests
pytest                              # All tests
pytest tests/test_foo.py            # Single file
pytest tests/test_foo.py::TestClass::test_method  # Single test
pytest -m unit                      # Unit tests only
pytest -m integration               # Integration tests only
pytest -m "not requires_mysql and not requires_ollama"  # Skip tests needing real services

# Lint & format
ruff check src/                     # Lint
ruff check --fix src/               # Auto-fix
ruff format src/                    # Format

# Type check
mypy src/rds_agent/

# Run services
python manage.py runserver 0.0.0.0:8000                          # Django web
celery -A rds_agent worker -l info --concurrency=5               # Celery worker
celery -A rds_agent beat -l info                                  # Celery beat scheduler
rds-agent api                                                     # FastAPI (uvicorn)
rds-agent chat                                                    # Interactive CLI chat

# Initialize knowledge base (loads knowledge/mysql/ into ChromaDB)
python scripts/init_knowledge.py
```

Tests requiring real MySQL or Ollama are auto-skipped unless `MYSQL_TEST_HOST` or `OLLAMA_TEST_ENABLED` env vars are set.

## Architecture

### Three-Layer Router System

All queries flow through `RouterAgent` (`src/rds_agent/router/agent.py`), which classifies questions and routes to one of three paths:

1. **SIMPLE_QA** → HermesAgent (Function Calling via Ollama/hermes3) + Knowledge Base (ChromaDB vector search)
2. **SOP_SKILL** → Skills/SOP Engine (standardized step-by-step diagnostic procedures)
3. **GENERAL** → LangGraph Agent (RDSAgent or DiagnosticAgent for autonomous planning)

`IterativeRouterAgent` extends `RouterAgent` with a self-iteration loop (evaluate → reflect → improve).

### Four Agent Systems

| Agent | Location | Framework | Model | Purpose |
|-------|----------|-----------|-------|---------|
| HermesAgent | `hermes/` | Function Calling | hermes3 | Simple Q&A, tool calls |
| Skills/SOP | `skills/` | SOP flow engine | Any | Standardized diagnosis (CPU, storage, SQL, connection) |
| RDSAgent | `core/` | LangGraph StateGraph | qwen2.5:14b | Medium-complexity Q&A |
| DiagnosticAgent | `diagnostic/` | LangGraph | qwen2.5:14b | Full 13-point inspection |

### Key Source Layout

Source code: `src/rds_agent/`

- `router/` — Three-layer classifier + router agent
- `agent/` — Self-iteration framework (BaseAgent, IterationLoop, ReflectionEngine)
- `hermes/` — Hermes Function Calling agent + ToolRegistry
- `skills/` — SOP engine: BaseSkill, SOPStep, MarkdownSkillParser, SkillGenerator; concrete skills in `cpu_skill.py`, `storage_skill.py`, `sql_skill.py`, `connection_skill.py`; docs in `skills/docs/`, sops in `skills/sops/`
- `core/` — LangGraph agent: StateGraph with nodes (classify → check_instance → select_tools → execute_tools → respond)
- `diagnostic/` — 13-point inspection, health checks, report generator, parameter optimizer
- `data/` — Data access layer: MySQL client, instance platform API, vector store, Pydantic models
- `tools/` — Tool layer (8+ categories): instance, performance, sql, connection, storage, parameters, knowledge, diagnostic
- `scheduler/` — Django app: models, services, Celery tasks, DRF API
- `api/` — FastAPI web API (alternative to Django endpoints)
- `django_project/` — Django project config (settings, urls, celery, wsgi)
- `utils/` — `config.py` (pydantic-settings), `logger.py` (rich-based)

### Key Design Patterns

- **Lazy-loaded singletons**: All agents use `get_xxx()` factory functions (e.g., `get_router_agent()`, `get_hermes_agent()`) with global `_instance` pattern
- **Pydantic-settings**: All config via env vars with typed settings classes using `env_prefix` (OLLAMA_, HERMES_, DB_, REDIS_, etc.)
- **LangGraph StateGraph**: Core and diagnostic agents use state machine graphs with conditional edges
- **SOP pattern**: Skills define multi-step Standard Operating Procedures with decision points
- **MarkdownSkillParser**: Dynamic skill generation from Markdown documents with YAML front matter
- **Dual API**: Both FastAPI (`api/`) and Django REST Framework (`scheduler/api/`) endpoints exist

### Configuration

Primary config: `src/rds_agent/utils/config.py` using pydantic-settings. Copy `.env.example` to `.env` and fill in values. Django settings at `src/rds_agent/django_project/settings.py`.

## Linting & Formatting Rules

- Ruff: line-length=100, target py310, rules E/F/I/N/W/UP/B, E501 ignored
- mypy: strict mode, python 3.10
