# Model Decision Matrix

| Task | Primary | Alternative | MVP |
|------|---------|------------|-----|
| Building | SegFormer-B2 | Mask2Former | YES |
| Road | SegFormer-B2 | DeepLabV3+ | YES |
| Land-use | SegFormer-B2 | Mask2Former | YES |
| Boundary evidence | SegFormer-B2 | Mask2Former | YES |
| Object detection | YOLO | RT-DETR | OPTIONAL |
| Parcel inference | GIS reasoning | GAT/GATv2 | GIS FIRST |
| Polygonization | GDAL / Shapely | — | YES |
| Topology | PostGIS / GEOS | — | YES |
| Old/new comparison | Spatial algorithms | — | YES |
| Change detection | Spatial algorithms | Siamese / ChangeTransformer | GIS FIRST |
| Confidence | Rule-based | XGBoost | RULE FIRST |
| GNSS | Geospatial validation | Optimization | YES |

## Why each choice

- **Building / Road / Land-use / Boundary — SegFormer-B2.** A strong,
  widely used encoder-decoder for semantic segmentation that is implemented
  out of the box by `segmentation-models-pytorch` (`mit_b2` encoder) and
  documented across the remote-sensing literature. Mask2Former stays wired as
  an alternative adapter for when instance-level masks matter.
- **YOLO optional.** Segmentation covers the MVP scope. YOLO adds value for
  counting/detecting specific objects (cars, roof elements) — kept behind the
  `yolo` adapter, not in the default pipeline.
- **Parcel inference — GIS reasoning first.** Parcels are legal constructs:
  building footprints ≠ parcels, roads ≠ parcels, walls ≠ legal boundaries.
  Deterministic geospatial reasoning (existing parcels + road offsets +
  boundary evidence + GNSS) is transparent and auditable — exactly what a
  cadastral workflow demands. A GAT/GATv2 model is a *future* refinement for
  modelling adjacency relationships, not a production dependency.
- **Polygonization — GDAL/Shapely.** Rasterio's `features.shapes` + GEOS
  repair is battle-tested, CRS-aware, and dependency-light.
- **Topology — PostGIS/GEOS.** The database already has spatial index and
  geometry repair; GLES/GEOS rules are the industry standard for boundary
  networks.
- **Old/new comparison — spatial algorithms.** Fewer columns on the report,
  and it needs no training data: intersection, IoU, displacement, Hausdorff.
- **Change detection — spatial algorithms first.** A Siamese / ChangeFormer
  transformer is a *future* accuracy upgrade; the deterministic flagging of
  NEW/SUBDIVISION/MERGER/CONFLICT works today against old cadastre.
- **Confidence — rules first.** No labelled training data exists yet for
  calibration, and rule weight sources live in config. XGBoost becomes viable
  once surveyor review outcomes provide ground truth.
- **GNSS — geospatial validation.** Distance-to-boundary checks, point-in-
  parcel matching, accuracy filtering. No learning required.