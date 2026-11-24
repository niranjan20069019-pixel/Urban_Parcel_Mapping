# GIS Workflow

```
Raster
  ↓ inspect (CRS, resolution, dimensions, bounds, nodata, transform)
  ↓ reproject/resample ONLY when explicitly requested
Tiling (512×512, 64 overlap, transform preserved)
  ↓ AI inference per tile
  ↓ prediction stitching (overlap-averaged)
Mask
  ↓ confidence filter
  ↓ morphological cleanup / noise removal
  ↓ connected components
  ↓ contour extraction
  ↓ polygon generation (rasterio.features.shapes)
  ↓ pixel → CRS coordinate conversion (affine per tile)
  ↓ simplification
  ↓ geometry repair (make_valid / buffer(0))
  ↓ topology validation + safe repair
Parcel inference (candidate generation)
  ↓ old/new comparison + change classification
Validation (GNSS, surveyor review)
Export (GeoJSON / GPKG / Shapefile / CSV / PostGIS)
```

## CRS best practices

- Inspect before anything: `app/gis/raster.inspect_raster()` returns
  CRS, resolution, bounds, nodata, transform, dtype.
- **Never silently change CRS.** All spatial ops first normalize to a common
  CRS. For area/perimeter, reproject into an equal-area/preserving CRS;
  `ensure_utm_crs(bounds)` auto-selects the UTM zone from the centroid.
- Geographic CRS (e.g. EPSG:4326) has degrees; lengths/areas in degrees are
  meaningless. Always compute metric measures in a projected CRS.
- Axis order: use `always_xy=True` on every `Transformer.from_crs` call to
  avoid lon/lat vs lat/lon surprises.

## Geometry hygiene

- `repair_geometry`: `shapely.validation.make_valid`, fallback `buffer(0)`.
- `simplify_geometry`: `simplify(tol, preserve_topology=True)` in CRS units.
- `mask_to_polygons`: drops polygons under `min_area`, reports the mean mask
  value inside each polygon as its confidence.
- `snap_to_grid` / hole removal: safe tail cleanups before DB insert.

## Topology checks (`app/gis/topology`)

- Overlaps (spatial-indexed pair search), gaps (interior rings of the union),
  self-intersections (invalid geometries), duplicates (`equals_exact`),
  slivers (area < threshold).
- `repair_topology` only auto-fixes safe issues (invalid geometry → valid,
  empty geometries dropped). Every change is returned in a log and persisted
  as a `topology_issues` row.

## Spatial indexing

`app/gis/spatial_index.py` wraps shapely STRtree for range queries,
nearest-neighbour, and bbox filtering. Also used in overlap/duplicate checks
and GNSS↔parcel matching, keeping large datasets sub-quadratic.