from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models import GnssPoint, Parcel, Project

T = TypeVar("T")


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, obj_id: int) -> T | None:
        return await self.session.get(self.model, obj_id)

    async def list(self, *, skip: int = 0, limit: int = 100) -> Sequence[T]:
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(self, **data) -> T:
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj_id: int, **data) -> T:
        obj = await self.get(obj_id)
        if obj is None:
            raise AppError(f"{self.model.__name__} #{obj_id} not found.")
        for key, value in data.items():
            setattr(obj, key, value)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj_id: int) -> bool:
        obj = await self.get(obj_id)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.commit()
        return True

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return int(result.scalar_one())


class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def get_by_name(self, name: str) -> Project | None:
        result = await self.session.execute(
            select(Project).where(Project.name == name)
        )
        return result.scalars().first()

    async def list_with_counts(self) -> list[dict]:
        result = await self.session.execute(
            select(
                Project,
                func.count(func.distinct(Parcel.id)).label("parcel_count"),
                func.count(func.distinct(GnssPoint.id)).label("gnss_count"),
            )
            .outerjoin(Parcel, Parcel.project_id == Project.id)
            .outerjoin(GnssPoint, GnssPoint.project_id == Project.id)
            .group_by(Project.id)
        )
        return [
            {
                "project": project,
                "parcel_count": parcel_count,
                "gnss_count": gnss_count,
            }
            for project, parcel_count, gnss_count in result.all()
        ]


class ParcelRepository(BaseRepository[Parcel]):
    model = Parcel

    def _project_filter(self, project_id: int | None):
        return [] if project_id is None else [Parcel.project_id == project_id]

    async def get_by_project(self, project_id: int) -> Sequence[Parcel]:
        result = await self.session.execute(
            select(Parcel)
            .where(Parcel.project_id == project_id)
            .order_by(Parcel.id)
        )
        return result.scalars().all()

    async def get_parcel_by_point(
        self, longitude: float, latitude: float, project_id: int | None = None
    ) -> Parcel | None:
        point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        stmt = select(Parcel).where(func.ST_Contains(Parcel.geom, point))
        if project_id is not None:
            stmt = stmt.where(Parcel.project_id == project_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_parcels_in_bbox(
        self,
        minx: float,
        miny: float,
        maxx: float,
        maxy: float,
        project_id: int | None = None,
    ) -> Sequence[Parcel]:
        envelope = func.ST_MakeEnvelope(minx, miny, maxx, maxy, 4326)
        stmt = select(Parcel).where(func.ST_Intersects(Parcel.geom, envelope))
        if project_id is not None:
            stmt = stmt.where(Parcel.project_id == project_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_latest_version(self, project_id: int, parent_parcel_id: int | None) -> int:
        stmt = select(func.coalesce(func.max(Parcel.version), 0)).where(
            Parcel.project_id == project_id
        )
        if parent_parcel_id is not None:
            stmt = stmt.where(Parcel.parent_parcel_id == parent_parcel_id)
        result = await self.session.execute(stmt)
        return int(result.scalar_one()) + 1


class GnssPointRepository(BaseRepository[GnssPoint]):
    model = GnssPoint

    async def get_by_project(self, project_id: int) -> Sequence[GnssPoint]:
        result = await self.session.execute(
            select(GnssPoint)
            .where(GnssPoint.project_id == project_id)
            .order_by(GnssPoint.id)
        )
        return result.scalars().all()

    async def get_in_bbox(
        self, minx: float, miny: float, maxx: float, maxy: float
    ) -> Sequence[GnssPoint]:
        envelope = func.ST_MakeEnvelope(minx, miny, maxx, maxy, 4326)
        result = await self.session.execute(
            select(GnssPoint).where(func.ST_Intersects(GnssPoint.geom, envelope))
        )
        return result.scalars().all()

    async def count_by_source(self, project_id: int) -> dict[str, int]:
        result = await self.session.execute(
            select(GnssPoint.source, func.count(GnssPoint.id))
            .where(GnssPoint.project_id == project_id)
            .group_by(GnssPoint.source)
        )
        return {source or "unknown": count for source, count in result.all()}