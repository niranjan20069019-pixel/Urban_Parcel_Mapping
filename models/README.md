# Model Checkpoints

## Directory Structure

```
models/
  checkpoints/
    building/      - Building segmentation (SegFormer, 2 classes)
    road/          - Road segmentation (SegFormer, 3 classes)
    landuse/       - Land use classification (SegFormer, 8 classes)
    boundary/      - Boundary detection (SegFormer, 4 classes)
  configs/         - YAML config per model
```

## Installation

1. Place trained weights at `models/checkpoints/<task>/model.pth`
2. Config files in `models/configs/<task>.yaml` define architecture and thresholds
3. Checkpoint paths in configs must match actual file locations

## Training

Models are SegFormer (MIT-B2 encoder) trained with:
- Input: 512x512 RGB tiles
- Optimizer: AdamW, lr=1e-4
- Scheduler: CosineAnnealingLR
- Augmentation: flips, rotation, scale, brightness/contrast

## Exporting from Training

```python
import torch
model.load_state_dict(torch.load("best_model.pth"))
torch.save(model.state_dict(), "model.pth")
```
