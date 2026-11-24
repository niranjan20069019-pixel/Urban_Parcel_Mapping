from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import Dataset, GnssPoint, Parcel, Project
from app.schemas.project import ProjectCreate, ProjectList, ProjectResponse, ProjectUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


async def _get_or_404(project_id: int, db: AsyncSession) -> Project:
    proj = await db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project #{project_id} not found")
    return proj


def _to_response(p: Project) -> ProjectResponse:
    return ProjectResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        status=p.status,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)) -> ProjectResponse:
    existing = await db.execute(select(Project).where(Project.name == body.name))
    if existing.scalars().first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Project '{body.name}' already exists")

    proj = Project(name=body.name, description=body.description)
    db.add(proj)
    await db.flush()
    await db.refresh(proj)
    logger.info("Created project %d: %s", proj.id, proj.name)
    return _to_response(proj)


@router.get("", response_model=ProjectList)
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> ProjectList:
    result = await db.execute(select(Project).offset(skip).limit(limit))
    projects = result.scalars().all()
    count_result = await db.execute(select(func.count()).select_from(Project))
    total = count_result.scalar_one()
    return ProjectList(projects=[_to_response(p) for p in projects], total=total)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)) -> ProjectResponse:
    proj = await _get_or_404(project_id, db)
    return _to_response(proj)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    proj = await _get_or_404(project_id, db)
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(proj, key, value)
    await db.flush()
    await db.refresh(proj)
    logger.info("Updated project %d", project_id)
    return _to_response(proj)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)) -> None:
    proj = await _get_or_404(project_id, db)
    await db.delete(proj)
    await db.flush()
    logger.info("Deleted project %d", project_id)


@router.get("/{project_id}/summary")
async def get_project_summary(project_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    proj = await _get_or_404(project_id, db)

    parcel_count = (await db.execute(
        select(func.count()).select_from(Parcel).where(Parcel.project_id == project_id)
    )).scalar_one()

    dataset_count = (await db.execute(
        select(func.count()).select_from(Dataset).where(Dataset.project_id == project_id)
    )).scalar_one()

    gnss_count = (await db.execute(
        select(func.count()).select_from(GnssPoint).where(GnssPoint.project_id == project_id)
    )).scalar_one()

    status_counts_result = await db.execute(
        select(Parcel.status, func.count()).where(Parcel.project_id == project_id).group_by(Parcel.status)
    )
    statuses = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in status_counts_result.all()}

    return {
        "project": _to_response(proj).model_dump(),
        "parcel_count": parcel_count,
        "dataset_count": dataset_count,
        "gnss_point_count": gnss_count,
        "parcel_statuses": statuses,
    }
