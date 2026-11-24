# GNSS Workflow

GNSS (incl. CORS) points are the authoritative ground-truth layer. The system
uses them to validate AI parcels — it never invents them and never uses mock
points as if they were real.

## Accepted formats

- CSV with columns such as `point_id, latitude, longitude, height, accuracy,
  timestamp, source`
- GeoJSON point layer
- PostGIS records via the API

Parsing is in `app/services/gnss_service.import_gnss_points`. CSV columns
are matched leniently (`latitude`/`lat`/`y`, `longitude`/`lon`/`x`,
`accuracy`/`precision`, `height`/`z`, `timestamp`/`time`).

## CRS handling

- If the file carries a CRS it is respected; otherwise the caller supplies
  `crs`. All points are normalized to EPSG:4326 for storage.
- Coordinates are stored as a POINT column (PostGIS) plus explicit lat/lon
  attributes for tabular use.

## Validation

`validate_gnss_accuracy(points, threshold)` flags points whose reported
accuracy exceeds the threshold (e.g. > 0.05 m), which indicates unusable
solutions.

## Parcel matching

`match_gnss_to_parcel` uses spatial index point-in-polygon to attach GNSS
points to parcels; `calculate_gnss_agreement` converts mean distance to an
agreement score fed into the confidence engine.

## Confidence contribution

GNSS agreement is one weighted factor in `ConfidenceFactor`; when no GNSS
exists the factor scores neutral (0.5) and the pipeline logs a warning rather
than guessing.

## Red flags (reported prominently)

- GNSS accuracy below the quality threshold → flag the point, never hide it.
- GNSS point outside every candidate parcel → surface for surveyor review.