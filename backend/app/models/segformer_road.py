"""Road / pathway SegFormer with polygon, centerline and connectivity extraction."""

from __future__ import annotations

from app.models.segformer_base import SegFormerAdapter


class SegFormerRoad(SegFormerAdapter):
    def __init__(self, checkpoint_path, device="auto", threshold=0.45,
                 encoder_name="mit_b0", input_size=512, **kwargs):
        super().__init__(checkpoint_path=checkpoint_path, device=device, num_classes=3,
                         class_mapping={0: "background", 1: "road", 2: "pathway"},
                         threshold=threshold, input_size=input_size,
                         encoder_name=encoder_name, **kwargs)

    def extract_polygons(self, mask, class_ids=None) -> dict:
        """Per-class polygons (list of [x, y] rings) via contour extraction."""
        import cv2
        import numpy as np

        if class_ids is None:
            class_ids = [c for c in self.class_mapping if c != 0]
        mask = np.asarray(mask)
        out = {}
        for cid in class_ids:
            m = np.where(mask == cid, 255, 0).astype(np.uint8)
            contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            out[cid] = [c.reshape(-1, 2).tolist() for c in contours]
        return out

    def extract_centerlines(self, mask) -> "np.ndarray":
        """Skeleton of the road+pathway union (1px centerlines)."""
        import numpy as np

        m = np.asarray(mask)
        return self.skeletonize((m > 0).astype(np.uint8))

    def connectivity_analysis(self, mask) -> dict:
        """Number / size / bbox of connected road components."""
        import cv2
        import numpy as np

        m = np.asarray(mask, dtype=np.uint8)
        if m.sum() == 0:
            return {"num_components": 0, "largest_area": 0, "components": []}
        n, labels, stats, _ = cv2.connectedComponentsWithStats(m, 8)
        components = []
        for i in range(1, n):
            components.append({
                "id": i,
                "area": int(stats[i, cv2.CC_STAT_AREA]),
                "bbox": [
                    int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP]),
                    int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT]),
                ],
            })
        components.sort(key=lambda c: c["area"], reverse=True)
        return {
            "num_components": n - 1,
            "largest_area": components[0]["area"] if components else 0,
            "components": components,
        }

    def get_road_network(self, mask) -> dict:
        return {
            "polygons": self.extract_polygons(mask),
            "centerlines": self.extract_centerlines(mask),
            "connectivity": self.connectivity_analysis(mask),
        }

    def predict(self, image) -> dict:
        result = super().predict(image)
        result["road_network"] = self.get_road_network(result["mask"])
        return result