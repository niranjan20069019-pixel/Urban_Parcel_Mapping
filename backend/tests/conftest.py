"""Shared pytest fixtures.

Skips DB-dependent tests when PostgreSQL/PostGIS is not reachable, so the
unit suite runs in a clean dev environment.
"""
from __future__ import annotations

import asyncio
import os

import pytest


def _database_reachable() -> bool:
    if os.environ.get("SKIP_DB_TESTS", "").lower() in ("1", "true", "yes"):
        return False
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/urban_cadastral",
    )

    async def _try_connect() -> bool:
        try:
            import asyncpg
            conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
            await conn.close()
            return True
        except Exception:
            return False

    try:
        return asyncio.run(_try_connect())
    except Exception:
        return False


db_available = pytest.mark.skipif(
    not _database_reachable(),
    reason="PostgreSQL/PostGIS not reachable with configured DATABASE_URL; skipping DB-integration tests",
)