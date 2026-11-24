from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    AppError,
    CRSError,
    DatasetError,
    ExportError,
    GNSSValidationError,
    InvalidGeometryError,
    InvalidRasterError,
    ModelInferenceError,
    ModelNotFoundError,
    TileError,
    TopologyError,
)
from app.core.logging import get_logger
from app.db.database import init_db
from app.api.routes import (
    comparison,
    export,
    features,
    gnss,
    imagery,
    inference,
    parcels,
    projects,
    surveyor,
    upload,
    validation,
)

logger = get_logger(__name__)

app = FastAPI(
    title="Urban Parcel Mapping API",
    description="End-to-end urban parcel mapping: imagery upload, AI inference, parcel generation, surveyor review, comparison, validation, and export.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = settings.API_PREFIX

for router in (
    projects,
    upload,
    imagery,
    inference,
    features,
    parcels,
    comparison,
    validation,
    gnss,
    surveyor,
    export,
):
    app.include_router(router.router, prefix=API_PREFIX)


@app.on_event("startup")
async def on_startup() -> None:
    settings.ensure_dirs()
    await init_db()
    logger.info("Startup complete: data dirs ensured, DB initialised.")


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "service": "urban-parcel-mapping", "version": app.version}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("%s (%s)", exc.message, type(exc).__name__)
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message, "error": type(exc).__name__, "details": exc.details},
    )


@app.exception_handler(TopologyError)
async def topology_error_handler(request: Request, exc: TopologyError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.message, "error": "TopologyError", "details": exc.details},
    )


@app.exception_handler(InvalidGeometryError)
async def invalid_geometry_handler(request: Request, exc: InvalidGeometryError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.message, "error": "InvalidGeometryError", "details": exc.details},
    )


@app.exception_handler(GNSSValidationError)
async def gnss_error_handler(request: Request, exc: GNSSValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.message, "error": "GNSSValidationError", "details": exc.details},
    )


@app.exception_handler(InvalidRasterError)
async def invalid_raster_handler(request: Request, exc: InvalidRasterError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.message, "error": "InvalidRasterError", "details": exc.details},
    )


@app.exception_handler(CRSError)
async def crs_error_handler(request: Request, exc: CRSError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.message, "error": "CRSError", "details": exc.details},
    )


@app.exception_handler(ModelNotFoundError)
async def model_not_found_handler(request: Request, exc: ModelNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": exc.message, "error": "ModelNotFoundError", "details": exc.details},
    )


@app.exception_handler(ModelInferenceError)
async def model_inference_handler(request: Request, exc: ModelInferenceError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": exc.message, "error": "ModelInferenceError", "details": exc.details},
    )


@app.exception_handler(DatasetError)
async def dataset_error_handler(request: Request, exc: DatasetError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message, "error": "DatasetError", "details": exc.details},
    )


@app.exception_handler(TileError)
async def tile_error_handler(request: Request, exc: TileError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message, "error": "TileError", "details": exc.details},
    )


@app.exception_handler(ExportError)
async def export_error_handler(request: Request, exc: ExportError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message, "error": "ExportError", "details": exc.details},
    )