# Dependency groups

Core Python: pydantic, pydantic-settings, sqlalchemy, psycopg, alembic.
Transport/reliability: httpx, tenacity, structlog.
Development/test: pytest, pytest-asyncio, mypy, ruff, jsonschema.
Strategy/ML dependencies are introduced only by the phase that needs them.
Frontend dependencies are isolated to apps/web.
