from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> DateTime:
    return DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


class GeometryModelMixin:
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ParcelStatus(str, enum.Enum):
    OLD = "OLD"
    AI_GENERATED = "AI_GENERATED"
    SURVEYOR_EDITED = "SURVEYOR_EDITED"
    GNSS_VALIDATED = "GNSS_VALIDATED"
    FINAL_VALIDATED = "FINAL_VALIDATED"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    datasets: Mapped[list["Dataset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    parcels: Mapped[list["Parcel"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    gnss_points: Mapped[list["GnssPoint"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    topology_issues: Mapped[list["TopologyIssue"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    parcel_changes: Mapped[list["ParcelChange"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="datasets")
    rasters: Mapped[list["Raster"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class Raster(Base):
    __tablename__ = "rasters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    crs: Mapped[str | None] = mapped_column(String(50), nullable=True)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    bands: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    resolution: Mapped[float | None] = mapped_column(Float, nullable=True)
    bounds_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    nodata: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    dataset: Mapped["Dataset"] = relationship(back_populates="rasters")
    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="raster", cascade="all, delete-orphan"
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raster_id: Mapped[int] = mapped_column(
        ForeignKey("rasters.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    checkpoint_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    class_mapping_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    raster: Mapped["Raster"] = relationship(back_populates="predictions")
    buildings: Mapped[list["Building"]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan"
    )
    roads: Mapped[list["Road"]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan"
    )
    landuse_features: Mapped[list["LanduseFeature"]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan"
    )
    boundary_evidences: Mapped[list["BoundaryEvidence"]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan"
    )


class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False
    )
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    perimeter: Mapped[float | None] = mapped_column(Float, nullable=True)
    centroid: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=True
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    prediction: Mapped["Prediction"] = relationship(back_populates="buildings")


class Road(Base):
    __tablename__ = "roads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False
    )
    centerline: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="MULTILINESTRING", srid=4326), nullable=True
    )
    road_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    length: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    prediction: Mapped["Prediction"] = relationship(back_populates="roads")


class LanduseFeature(Base):
    __tablename__ = "landuse_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False
    )
    landuse_class: Mapped[str] = mapped_column(String(50), nullable=False)
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    prediction: Mapped["Prediction"] = relationship(back_populates="landuse_features")


class BoundaryEvidence(Base):
    __tablename__ = "boundary_evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTILINESTRING", srid=4326), nullable=False
    )
    boundary_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    prediction: Mapped["Prediction"] = relationship(back_populates="boundary_evidences")


class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[ParcelStatus] = mapped_column(
        Enum(ParcelStatus, name="parcel_status"),
        nullable=False,
        default=ParcelStatus.OLD,
    )
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    perimeter: Mapped[float | None] = mapped_column(Float, nullable=True)
    centroid: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=True
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parent_parcel_id: Mapped[int | None] = mapped_column(
        ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="parcels")
    parent_parcel: Mapped["Parcel | None"] = relationship(
        foreign_keys=[parent_parcel_id], remote_side="Parcel.id"
    )
    validations: Mapped[list["Validation"]] = relationship(
        back_populates="parcel", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="parcel", cascade="all, delete-orphan"
    )
    surveyor_edits: Mapped[list["SurveyorEdit"]] = relationship(
        back_populates="parcel", cascade="all, delete-orphan"
    )


class GnssPoint(Base):
    __tablename__ = "gnss_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    point_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326), nullable=False
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(_now(), nullable=True)
    crs: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="gnss_points")


class Validation(Base):
    __tablename__ = "validations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parcel_id: Mapped[int] = mapped_column(
        ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False
    )
    validator: Mapped[str] = mapped_column(String(100), nullable=False)
    validation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    parcel: Mapped["Parcel"] = relationship(back_populates="validations")


class TopologyIssue(Base):
    __tablename__ = "topology_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    parcel_id: Mapped[int | None] = mapped_column(
        ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True
    )
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    geom: Mapped[Any | None] = mapped_column(Geometry(srid=4326), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="topology_issues")


class ParcelChange(Base):
    __tablename__ = "parcel_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    old_parcel_id: Mapped[int | None] = mapped_column(
        ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True
    )
    new_parcel_id: Mapped[int | None] = mapped_column(
        ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True
    )
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="parcel_changes")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parcel_id: Mapped[int] = mapped_column(
        ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(_now(), nullable=True)

    parcel: Mapped["Parcel"] = relationship(back_populates="recommendations")


class SurveyorEdit(Base):
    __tablename__ = "surveyor_edits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parcel_id: Mapped[int] = mapped_column(
        ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False
    )
    editor: Mapped[str] = mapped_column(String(100), nullable=False)
    old_geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False
    )
    new_geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _now(), server_default=func.now(), nullable=False
    )

    parcel: Mapped["Parcel"] = relationship(back_populates="surveyor_edits")