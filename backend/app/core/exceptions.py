from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error with an optional details payload."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        return self.message


class InvalidRasterError(AppError):
    """Raised when a raster file is corrupt, unreadable, or unsupported."""


class CRSError(AppError):
    """Raised when a CRS is missing, unrecognized, or conflicts between layers."""


class ModelNotFoundError(AppError):
    """Raised when a model checkpoint path does not exist."""


class ModelInferenceError(AppError):
    """Raised when model inference fails at runtime."""


class InvalidGeometryError(AppError):
    """Raised when input geometry is invalid or malformed."""


class TopologyError(AppError):
    """Raised when geometry operations break topological consistency."""


class GNSSValidationError(AppError):
    """Raised when GNSS survey data fails validation."""


class DatasetError(AppError):
    """Raised for generic dataset ingestion/lookup failures."""


class TileError(AppError):
    """Raised when tiling/untiling operations fail."""


class ExportError(AppError):
    """Raised when exporting results to a file or format fails."""