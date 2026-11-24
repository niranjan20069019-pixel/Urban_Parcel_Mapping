"""Building footprint SegFormer (background / building)."""

from __future__ import annotations

from app.models.segformer_base import SegFormerAdapter


class SegFormerBuilding(SegFormerAdapter):
    def __init__(self, checkpoint_path, device="auto", threshold=0.6,
                 encoder_name="mit_b0", input_size=512, **kwargs):
        # Higher default threshold keeps low-confidence building pixels out.
        super().__init__(checkpoint_path=checkpoint_path, device=device, num_classes=2,
                         class_mapping={0: "background", 1: "building"},
                         threshold=threshold, input_size=input_size,
                         encoder_name=encoder_name, **kwargs)

    @staticmethod
    def clean_mask(mask, kernel_size=5):
        """Morphological open (drop speckles) then close (fill holes) a building mask."""
        import cv2
        import numpy as np

        m = np.asarray(mask, dtype=np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
        return m

    def predict(self, image) -> dict:
        result = super().predict(image)
        result["mask"] = self.clean_mask(result["mask"])
        return result