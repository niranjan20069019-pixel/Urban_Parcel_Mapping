# Change Detection

## Scope

"Change" means **cadastral change between the OLD registered parcel layer and
the newly inferred AI layer** — measured with spatial algorithms, not with
image-differencing.

## Pipeline

```
OLD parcels (# polygons)   → normalize CRS + repair geometries
NEW AI parcels             → normalize CRS + repair geometries
        ↓ match by maximum IoU
        ↓ metrics per pair
```

## Metrics

`app/services/comparison_service.compare_parcel_sets` returns per record:

| Metric | Meaning |
|--------|---------|
| `iou` | Intersection over union of matched old/new |
| `area_difference` | signed new − old area |
| `centroid_distance` | distance between centroids |
| `boundary_displacement` | mean distance between sampled boundary rings |
| `hausdorff_distance` | worst-case boundary distance |

## Change classification

`app/services/change_detection_service` maps metrics to types:

| Type | Trigger |
|------|---------|
| `UNCHANGED` | IoU high, displacement below threshold |
| `BOUNDARY_SHIFT` | IoU moderate, consistent boundary movement |
| `SUBDIVISION` | one old parcel overlaps ≥2 new parcels |
| `MERGER` | ≥2 old parcels overlap one new parcel |
| `NEW` | new parcel with no old match |
| `REMOVED` | old parcel with no new match |
| `CONFLICT` | overlapping but incompatible edges |
| `UNCERTAIN` | metrics on no clear side of thresholds |

Thresholds live in `app/services/change_detection_service` as module
constants; adjust only with calibration evidence. Each classification stores
its evidence (the metrics above) so the reason is auditable.

## Future AI change detection

Two adapters exist but are **off by default**:

- `SiameseChangeAdapter` — bi-temporal image encoder; v1 falls back to
  pixel/structural diff when no checkpoint is present.
- `ChangeTransformerAdapter` — transformer change segmentation; v1 falls back
  to an SSIM-style structural diff.

They are intended to detect **visual change** (new construction, removal)
across image epochs — a different, complementary signal to the cadastral
old-vs-new comparison above. Enabling them does not change parcel status
logic; their outputs feed the evidence panel only.