# Model Training

Each primary model is trained separately with the same recipe:

```
Labelled dataset
  → annotation (QGIS vector → raster masks)
  → tiling (512×512)
  → geographically sound train/val/test split
  → train (SegFormer-B2 via segmentation-models-pytorch)
  → validate (IoU, mIoU, Dice/F1, Precision, Recall)
  → export checkpoint
  → copy to models/checkpoints/<task>/
  → configure .env
  → run inference
```

The human developer supplies the labelled drone/remote-sensing dataset and
runs the training. The application only needs the resulting checkpoint.

## Building SegFormer (background / building)

- Labels: vector building footprints → rasterized binary mask (pixel = 1
  inside footprint).
- Loss: CrossEntropy (or Dice), metric: IoU + polygon IoU on validation.
- After training, export weights and place them at
  `models/checkpoints/building/model.pth`.

## Road SegFormer (background / road / pathway)

- Labels: road + pathway network masks.
- Metrics: class IoU, plus centerline quality and connectivity on validation.
- Checkpoint → `models/checkpoints/road/model.pth`.

## Land-use SegFormer

- Labels: per-class polygons → raster class mask (`residential`, `commercial`,
  `industrial`, `vegetation`, `water`, `bare_land`, `road`…).
- Keep the class↔id mapping identical between training and inference; the
  app reads it from `models/configs/landuse.yaml`.
- Checkpoint → `models/checkpoints/landuse/model.pth`.

## Boundary SegFormer (boundary / wall / fence)

- Labels: physical boundary evidence only (walls, fences, hedges, visible
  boundary markers). Never label inferred/approximate legal boundaries.
- Metrics: point-recall@tolerance for boundary lines, class IoU.
- Checkpoint → `models/checkpoints/boundary/model.pth`.

## Geographic split (critical)

Do **not** randomly split tiles that may be adjacent or in the same block
into train and test.  Neighbouring imagery is nearly identical; a random
split overstates accuracy.  Use spatial separation:

```
Area A → training
Area B → validation
Area C → testing
```

Spatial leakage inflates IoU and hides overfitting. Keep a minimum buffer
(e.g. 50 m) between splits.

## Dataset sources & licensing

- SpaceNet datasets: usable for research; verify APL/commercial terms before
  production use.
- LoveDA: verify the licence for your use case.
- Custom drone/ORI imagery labelled in QGIS: check you own the rights and the
  flights were lawful.
- Always record licence + source per dataset in `models/README.md`.

## Annotation with QGIS

1. Create a polygon layer per feature (buildings, roads, landuse, boundary).
2. Digitize; snap on shared boundaries where appropriate.
3. Rasterize: `Raster → Conversion → Rasterize` toward a template GeoTIFF so
   masks align exactly with imagery tiles.
4. Attribute values become class ids (0 = background).
5. Tile the imagery and masks with identical geometry then train.

## Evaluation checklist

- [ ] mIoU reported per class
- [ ] geographic split respected
- [ ] class balance stated (background often dominates — expect inflated mIoU)
- [ ] checkpoint reproducible (record encoder, input size, epochs) in `models/README.md`