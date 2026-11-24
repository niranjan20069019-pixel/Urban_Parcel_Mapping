# Data Flow

## End to end

```
Drone ORI (GeoTIFF)  --upload-->  data/project_{id}/raw/
DSM / DTM            --upload-->  data/project_{id}/raw/
Old parcel GIS       --upload-->  data/project_{id}/raw/
GNSS (CSV/GeoJSON)   --upload-->  data/project_{id}/raw/
        │
        ▼
CRS / quality check          app/gis/raster.inspect_raster()
        │
        ▼
Tiling (512×512, 64 overlap) app/services/tiling_service.tile_raster()
        │
        ▼
Per-model inference          app/models/*  (or DEMO_MODE mock)
        │
        ▼
Masks (data/project_{id}/predictions/{model}_masks/*.npy)
        │
        ▼
Mask → polygons              app/gis/geometry.mask_to_polygons()
        │
        ▼
GIS vector layers            PostGIS: buildings / roads / landuse / boundary_evidences
        │
        ▼
Parcel inference             app/services/parcel_inference_service.infer_parcels()
        │
        ▼
Candidate parcels            PostGIS: parcels (status = AI_GENERATED)
        │
        ▼
Topology QA + repair         app/gis/topology + app/services/topology_service
        │
        ▼
Confidence engine            app/services/confidence_service
        │
        ▼
Old/New comparison           app/services/comparison_service  → parcel_changes
        │
        ▼
Change classification        UNCHANGED/BOUNDARY_SHIFT/SUBDIVISION/MERGER/NEW/REMOVED/CONFLICT/UNCERTAIN
        │
        ▼
Recommendations              app/services/recommendation_service
        │
        ▼
Surveyor review (WebGIS)     accept / edit / field-verify / notes
        │
        ▼
GNSS validation              app/services/gnss_service
        │
        ▼
Final validation             status = FINAL_VALIDATED
        │
        ▼
Export                       GeoJSON / GPKG / Shapefile / CSV (data/project_{id}/exports/)
```

## File layout

Every project is self-contained under `data/project_{id}/`:

| Directory | Content |
|-----------|---------|
| `raw/` | Uploaded source files (ORI, DSM, DTM, old GIS, GNSS) |
| `tiles/` | `tile_{row}_{col}.png` + `tiles_meta.json` (transform per tile) |
| `predictions/` | `{model}_masks/*.npy` per-tile masks |
| `vectors/` | Vectorized features before DB persistence |
| `parcels/` | Candidate/edited parcel layers |
| `exports/` | Final GeoJSON/GPKG/Shapefile/CSV |
| `gnss/` | GNSS evidence layers (if materialized to disk) |

## Standardisation rules

- CRS is preserved, never silently changed. Reprojection requires an explicit
  request (`POST /datasets/{id}/reproject`).
- Masks are stored in pixel space per tile; the georeferenced transform is
  kept in `tiles_meta.json` so downstream vectorization can convert to CRS.
- Model outputs are versioned: every `predictions` row records model name,
  checkpoint path, class mapping, file path and timestamp.

## Warnings, not crashes

- Missing DSM/DTM → warning; nDSM simply not computed.
- Missing GNSS → confidence factor reported as unknown, not fatal.
- Missing old parcel GIS → comparison skips gracefully (NEW classification).
- Missing checkpoint / missing model → ModelNotFoundError with the configured
  path and install instructions; the affected pipeline is disabled while the
  rest of the application stays operational.