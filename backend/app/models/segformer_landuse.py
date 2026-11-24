"""Land-use classification SegFormer (8 default classes, YAML-configurable mapping)."""

from __future__ import annotations

from pathlib import Path

from app.models.segformer_base import SegFormerAdapter

DEFAULT_LANDUSE_MAPPING = {
    0: "background",
    1: "residential",
    2: "commercial",
    3: "industrial",
    4: "vegetation",
    5: "water",
    6: "bare_land",
    7: "road",
}


class SegFormerLanduse(SegFormerAdapter):
    def __init__(self, checkpoint_path, device="auto", threshold=0.4,
                 encoder_name="mit_b0", input_size=512, class_mapping=None,
                 class_mapping_yaml=None, min_areas=None, **kwargs):
        mapping = dict(DEFAULT_LANDUSE_MAPPING)
        if class_mapping:
            mapping.update({int(k): v for k, v in class_mapping.items()})

        yaml_min_areas = {}
        if class_mapping_yaml:
            yaml_mapping, yaml_min_areas = self._load_yaml(class_mapping_yaml)
            mapping.update(yaml_mapping)

        merged_min_areas = dict(yaml_min_areas)
        if min_areas:
            merged_min_areas.update({int(k): int(v) for k, v in min_areas.items()})

        num_classes = max(mapping) + 1
        super().__init__(checkpoint_path=checkpoint_path, device=device,
                         num_classes=num_classes, class_mapping=mapping,
                         threshold=threshold, input_size=input_size, encoder_name=encoder_name)
        self.min_areas: dict[int, int] = merged_min_areas

    @staticmethod
    def _load_yaml(path) -> tuple[dict, dict]:
        import yaml

        with open(Path(path)) as f:
            data = yaml.safe_load(f) or {}
        mapping = {int(k): v for k, v in (data.get("class_mapping") or {}).items()}
        min_areas = {int(k): int(v) for k, v in (data.get("min_areas") or {}).items()}
        return mapping, min_areas

    def filter_small_regions(self, mask, min_areas=None):
        """Drop connected regions smaller than the per-class minimum pixel area."""
        import cv2
        import numpy as np

        areas = {**(self.min_areas or {}), **(min_areas or {})}
        if not areas:
            return np.asarray(mask)
        out = np.asarray(mask).copy()
        for label, min_area in areas.items():
            if label == 0:
                continue
            region = (out == label).astype(np.uint8)
            n, labels, stats, _ = cv2.connectedComponentsWithStats(region, 8)
            for i in range(1, n):
                if stats[i, cv2.CC_STAT_AREA] < min_area:
                    out[labels == i] = 0
        return out

    def predict(self, image) -> dict:
        result = super().predict(image)
        if self.min_areas:
            result["mask"] = self.filter_small_regions(result["mask"])
        return result