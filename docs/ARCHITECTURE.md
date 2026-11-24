# Architecture — Urban Parcel Mapping & Cadastral Feature Extraction

## System Model

AI is the **perception layer**, not the author of the cadastral record. Every
AI-generated geometry is provisional: a candidate that must pass topology,
comparison, GNSS and surveyor review before it can be called a parcel.

Core separation:

```
AI perception (semantic segmentation)
        +
Geospatial reasoning (tiling, vectorization, topology, CRS)
        +
Existing cadastral information (old parcel GIS)
        +
DSM/DTM + GNSS evidence
        +
Surveyor review
        =  candidate parcel
```

## Layers

| Layer | Components | Responsibility |
|-------|-----------|----------------|
| Presentation | React + TypeScript + MapLibre GL (`frontend/`) | WebGIS, layer control, parcel editing, surveyor review |
| API | FastAPI (`backend/app/api/routes/`) | REST endpoints for upload, inference, parcels, comparison, GNSS, exports |
| Services | `backend/app/services/` | Orchestrates ingestion, tiling, inference, vectorization, parcel inference, topology, confidence, comparison, recommendations |
| GIS | `backend/app/gis/` | Pure geospatial algorithms: raster I/O, CRS, geometry repair, topology, spatial indexing, distance metrics |
| Models | `backend/app/models/` | Adapter classes: SegFormer (building/road/landuse/boundary), Mask2Former, YOLO, GAT, Siamese, ChangeTransformer, XGBoost |
| Database | PostgreSQL + PostGIS (`backend/app/db/`) | Projects, datasets, rasters, predictions, features, parcels (+ version history), GNSS, validation, changes, recommendations |
| Storage | `data/project_{id}/` | Per-project `raw/ processed/ tiles/ predictions/ vectors/ parcels/ gnss/ exports/` |

## Runtime Flow

1. **Upload** — raster (GeoTIFF ORI/DSM/DTM), vector (existing parcels), or GNSS files land in `data/project_{id}/raw/`; metadata rows are written to PostGIS.
2. **Inspect & normalize** — CRS, resolution, bounds, nodata, transform; reproject/resample only when explicitly requested.
3. **Tile** — large GeoTIFF is split into 512×512 tiles with 64 px overlap; each tile keeps its georeferenced transform.
4. **Inference** — each enabled model processes tiles (batch on GPU, sequential on CPU); masks saved as `.npy`; **mock mode produces explicitly-labelled DEVELOPMENT MOCK output**.
5. **Vectorize** — masks → confidence filter → morphological cleanup → connected components → contours → polygons → reprojection → simplification → repair → GeoJSON/GPKG.
6. **Parcel inference** — combines existing parcels, roads, buildings, boundary evidence, land use, GNSS, DEM into candidate parcels via deterministic geospatial reasoning.
7. **Topology QA** — overlap/gap/self-intersection/duplicate/sliver checks; only safe repairs are auto-applied and every repair is logged.
8. **Confidence** — weighted rule engine (weights live in config, not code).
9. **Old/New comparison** — IoU, area difference, centroid/boundary displacement, Hausdorff distance → change classification.
10. **Recommendations** — transparent rule-based actions per parcel.
11. **Surveyor review** — accept/reject/edit/field-verify/annotate in the WebGIS.
12. **Validation** — GNSS matching, then FINAL_VALIDATED.
13. **Export** — GeoJSON / GeoPackage / Shapefile / CSV / PostGIS.

## Status Model

`OLD → AI_GENERATED → SURVEYOR_EDITED → GNSS_VALIDATED → FINAL_VALIDATED`

No AI-generated boundary is ever treated as a legally authoritative cadastral
boundary; that designation only follows surveyor + GNSS validation.