"""Deterministic development-mock segmentation.

Every output generated here is a synthetic placeholder and MUST be labelled
`DEVELOPMENT MOCK — NOT AI PREDICTION`.  Use to exercise the pipeline end to
end before a trained checkpoint exists.  Never treat mock output as real AI.
"""

from __future__ import annotations

import numpy as np

MOCK_LABEL = "DEVELOPMENT MOCK — NOT AI PREDICTION"

# Simple pattern for each model: blocks placed on a fixed grid, scaled by the
# input size so results are deterministic across tiles.
_MOCK_PATTERNS = {
    "building": [
        (0.10, 0.10, 0.18, 0.18, 1), (0.62, 0.35, 0.25, 0.20, 1),
        (0.30, 0.55, 0.16, 0.14, 1), (0.75, 0.70, 0.14, 0.16, 1),
    ],
    "road": [
        (0.20, 0.05, 0.06, 0.90, 1), (0.05, 0.55, 0.90, 0.06, 1),
        (0.65, 0.20, 0.10, 0.30, 2),
    ],
    "landuse": [
        (0.00, 0.00, 0.40, 0.50, 1), (0.40, 0.00, 0.60, 0.40, 2),
        (0.00, 0.50, 0.35, 0.50, 4), (0.35, 0.50, 0.65, 0.50, 6),
    ],
    "boundary": [
        (0.10, 0.10, 0.20, 0.02, 1), (0.40, 0.10, 0.20, 0.02, 1),
        (0.10, 0.30, 0.02, 0.30, 1), (0.20, 0.50, 0.15, 0.02, 1),
    ],
}


def build_mock_mask(image, model_name: str, seed: int = 0) -> dict:
    """Return a deterministic mock segmentation prediction for *model_name*.

    ``image`` may be HWC or (C,H,W); only its spatial size is used.
    """
    arr = np.asarray(image)
    if arr.ndim == 3 and arr.shape[0] in (1, 3, 4) and arr.shape[2] not in (1, 3, 4):
        h, w = arr.shape[1], arr.shape[2]
    else:
        h, w = arr.shape[0], arr.shape[1]

    rng = np.random.RandomState(seed)
    mask = np.zeros((h, w), dtype=np.int32)

    blocks = _MOCK_PATTERNS.get(model_name, _MOCK_PATTERNS["building"])
    for (nx, ny, bw, bh, cls) in blocks:
        x0, y0 = int(nx * w), int(ny * h)
        x1, y1 = min(w, x0 + int(bw * w)), min(h, y0 + int(bh * h))
        mask[y0:y1, x0:x1] = cls

    # deterministic noise speckle so confidence varies
    noise = rng.rand(*mask.shape)
    confidence = np.where(mask > 0, 0.75 + 0.2 * noise, np.zeros_like(noise))

    return {
        "mask": mask,
        "confidence": confidence,
        "probabilities": np.stack([1 - confidence, confidence] if mask.max() < 2
                                  else [np.full_like(confidence, 0.3), confidence], axis=-1),
        "logits": None,
        "is_mock": True,
        "mock_label": MOCK_LABEL,
    }


def project_dir(project_id: int):
    from app.core.config import settings
    return settings.DATA_DIR / f"project_{project_id}"