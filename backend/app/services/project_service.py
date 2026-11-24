from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.models import Dataset, Project

logger = get_logger(__name__)


async def create_project(db: AsyncSession, name: str, description: str | None = None) -> Project:
    project = Project(name=name, description=description)
    db.add(project)
    await db.flush()
    await db.refresh(project)
    logger.info("Created project %s (id=%d)", name, project.id)
    return project


async def get_project(db: AsyncSession, project_id: int) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise AppError(f"Project #{project_id} not found.")
    return project


async def list_projects(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Project]:
    result = await db.execute(select(Project).offset(skip).limit(limit))
    return list(result.scalars().all())


async def update_project(db: AsyncSession, project_id: int, **kwargs) -> Project:
    project = await get_project(db, project_id)
    for key, value in kwargs.items():
        if hasattr(project, key) and key not in ("id", "created_at"):
            setattr(project, key, value)
    await db.flush()
    await db.refresh(project)
    logger.info("Updated project %d", project_id)
    return project


async def delete_project(db: AsyncSession, project_id: int) -> bool:
    project = await db.get(Project, project_id)
    if project is None:
        return False
    await db.delete(project)
    await db.flush()
    logger.info("Deleted project %d", project_id)
    return True


async def get_project_datasets(db: AsyncSession, project_id: int) -> list[Dataset]:
    result = await db.execute(
        select(Dataset).where(Dataset.project_id == project_id).order_by(Dataset.id)
    )
    return list(result.scalars().all())
