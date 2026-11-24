"""Parcel boundary SegFormer (background / boundary / wall / fence)."""

from __future__ import annotations

from app.models.segformer_base import SegFormerAdapter


class SegFormerBoundary(SegFormerAdapter):
    def __init__(self, checkpoint_path, device="auto", threshold=0.35,
                 encoder_name="mit_b0", input_size=512, **kwargs):
        super().__init__(checkpoint_path=checkpoint_path, device=device, num_classes=4,
                         class_mapping={0: "background", 1: "boundary", 2: "wall", 3: "fence"},
                         threshold=threshold, input_size=input_size,
                         encoder_name=encoder_name, **kwargs)

    @staticmethod
    def fill_gaps(mask, kernel_size=3):
        """Close small breaks in boundary lines, then dilate to rejoin them."""
        import cv2
        import numpy as np

        m = np.asarray(mask, dtype=np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        closed = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
        return cv2.dilate(closed, kernel)

    def extract_lines(self, mask) -> dict:
        """1px skeleton of all linear classes; gap-filled first for continuity."""
        filled = self.fill_gaps(mask)
        return {"skeleton": self.skeletonize(filled), "filled_mask": filled}

    def predict(self, image) -> dict:
        result = super().predict(image)
        result["lines"] = self.extract_lines(result["mask"])
        return result