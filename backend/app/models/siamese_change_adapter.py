"""Siamese-change-detection adapter for bi-temporal parcel comparisons.

Requires a trained Siamese encoder checkpoint. When no checkpoint is provided,
the adapter operates in a pixel-diff fallback mode suitable for development.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from app.models.base import BaseModelAdapter

logger = logging.getLogger(__name__)


class SiameseChangeAdapter(BaseModelAdapter):
    """Bi-temporal change detection via Siamese encoder.

    In fallback mode (no checkpoint), computes absolute pixel difference
    with Gaussian blur + Otsu threshold. Replace with a real trained model
    for production use.
    """

    def __init__(self, checkpoint_path, device="auto", num_classes=2,
                 class_mapping=None, threshold=0.5, input_size=512, **kwargs):
        super().__init__(checkpoint_path=checkpoint_path, device=device,
                         num_classes=num_classes, class_mapping=class_mapping)
        self.threshold = threshold
        self.input_size = input_size
        self._fallback_mode = True

    def load_model(self) -> None:
        path = Path(self.checkpoint_path)
        if not path.exists():
            logger.warning(
                "Siamese checkpoint not found at %s — using pixel-diff fallback. "
                "Train a Siamese model and place checkpoint at the configured path.",
                path,
            )
            self._fallback_mode = True
            self.loaded = True
            return

        try:
            import torch
            self.model = torch.jit.load(str(path), map_location=self.device)
            self.model.eval()
            self._fallback_mode = False
            self.loaded = True
            logger.info("Loaded Siamese checkpoint from %s", path)
        except Exception as exc:
            logger.warning("Failed to load Siamese checkpoint: %s — falling back to pixel diff.", exc)
            self._fallback_mode = True
            self.loaded = True

    def preprocess(self, image):
        return image

    def predict(self, image) -> dict:
        """image must be a dict with 'image_t0' and 'image_t1' keys, each HWC."""
        if isinstance(image, dict):
            img_t0 = image.get("image_t0", image)
            img_t1 = image.get("image_t1", image)
        else:
            img_t0 = image
            img_t1 = image

        if self._fallback_mode:
            return self._pixel_diff_fallback(img_t0, img_t1)

        import torch
        t0 = self._to_tensor(img_t0)
        t1 = self._to_tensor(img_t1)
        with torch.inference_mode():
            out = self.model(t0, t1)
        if isinstance(out, dict):
            mask = out.get("mask", out.get("change_mask"))
        else:
            mask = out
        if hasattr(mask, "cpu"):
            mask = mask.cpu().numpy()
        return {"mask": np.asarray(mask, dtype=np.int32).squeeze()}

    def _pixel_diff_fallback(self, img_t0, img_t1) -> dict:
        a = np.asarray(img_t0, dtype=np.float32)
        b = np.asarray(img_t1, dtype=np.float32)
        if a.ndim == 2:
            a = np.stack([a] * 3, axis=-1)
        if b.ndim == 2:
            b = np.stack([b] * 3, axis=-1)
        diff = np.abs(a - b).mean(axis=-1)
        try:
            import cv2
            diff_blur = cv2.GaussianBlur(diff, (5, 5), 0)
            _, mask = cv2.threshold(
                diff_blur.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
        except ImportError:
            mask = (diff > self.threshold * 255).astype(np.uint8) * 255
        return {"mask": (mask > 0).astype(np.int32), "confidence": diff / 255.0}

    def _to_tensor(self, image):
        import torch
        img = np.asarray(image, dtype=np.float32) / 255.0
        if img.ndim == 2:
            img = np.stack([img] * 3, axis=-1)
        t = torch.from_numpy(img.transpose(2, 0, 1)).unsqueeze(0)
        return t.to(self.device)

    def postprocess(self, raw_output) -> dict:
        if isinstance(raw_output, dict):
            return raw_output
        return {"mask": np.asarray(raw_output, dtype=np.int32)}
