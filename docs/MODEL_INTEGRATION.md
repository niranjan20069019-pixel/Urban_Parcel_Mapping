# Model Integration

The human developer **does not need to touch Python source** to add trained
checkpoints. Everything below is configuration + placement.

## 1. Where to put a model

Each checkpoint goes in its reserved directory:

```
models/checkpoints/building/model.pth      # building segmentation (2 classes)
models/checkpoints/road/model.pth          # road + pathway (3 classes)
models/checkpoints/landuse/model.pth       # land use (configurable classes)
models/checkpoints/boundary/model.pth      # boundary evidence (4 classes)
```

`models/checkpoints/*/` is gitignored — weights never enter version control.

## 2. How to configure

Paths live in `.env` (copy `.env.example`):

```
BUILDING_MODEL_CHECKPOINT=models/checkpoints/building/model.pth
ROAD_MODEL_CHECKPOINT=models/checkpoints/road/model.pth
LANDUSE_MODEL_CHECKPOINT=models/checkpoints/landuse/model.pth
BOUNDARY_MODEL_CHECKPOINT=models/checkpoints/boundary/model.pth
```

Per-task YAML files (`models/configs/*.yaml`) carry model-level settings:
architecture, encoder, input size, class mapping, min area filters.  They are
the source of truth for class names.

## 3. How the application loads a model

```
POST /api/v1/projects/{id}/inference/{model}
```

`app/api/routes/inference._get_adapter` registers an adapter in the
singleton `registry` (a `ModelRegistry` from `app/models/segmentation_base`)
if it is not already present, instantiates it with the checkpoint from
`.env`, and calls `adapter.load_model()`.

If the checkpoint is missing:
- the API returns `404 ModelNotFoundError` with the configured path;
- the per-model inference endpoint reports the model as unavailable and
  disables **only** that model — other models and the rest of the app keep
  working.

## 4. Expected input / preprocessing

- Input: 3-band RGB (ORI). DSM/DTM are optional auxiliary evidence, **not**
  model input in the MVP.
- Preprocessing: resize to `input_size` (default 512), scale to `[0,1]`,
  normalize with ImageNet mean/std, `(1,C,H,W)` float32 tensor.
- To add channels later (`[R,G,B,DSM,DTM,nDSM]`): change `in_channels` in
  the SegFormer config, extend `normalize_image` for 6-band tensors, and
  stack the extra bands in the data loader. The adapter already passes
  `in_channels` through.

## 5. Inference / output

- Forward pass returns logits → softmax probabilities → mask + confidence.
- `postprocess` snaps the mask back to the **original tile size** and returns:
  - `mask` `(H,W)` int32 (class indices)
  - `confidence` `(H,W)` float max-class probability
  - `probabilities` `(H,W,C)` float
- Mock mode (`DEMO_MODE=true`) returns the same shape but is labelled
  `DEVELOPMENT MOCK — NOT AI PREDICTION`.

## 6. Class mapping

| Model | Classes |
|-------|---------|
| building | `0=background, 1=building` |
| road | `0=background, 1=road, 2=pathway` |
| landuse | `0=background, 1=residential, 2=commercial, 3=industrial, 4=vegetation, 5=water, 6=bare_land, 7=road` (configurable via YAML) |
| boundary | `0=background, 1=boundary, 2=wall, 3=fence` |

## 7. GPU / CPU fallback

`DEVICE=auto` (default) picks CUDA when `torch.cuda.is_available()` else CPU.
`GPU_ENABLED=true` forces CUDA. Missing GPU never breaks startup — CPU is used.

## 8. Versioning / reproducibility

Every prediction row stores: `model_name`, `model_version`, `checkpoint_path`,
`class_mapping`, `file_path`, `created_at`.  Combined with
`tiles_meta.json` (transform/CRS per tile) every AI result is reproducible.