"""Optional YOLO object-detection adapter (ultralytics backend)."""

from __future__ import annotations

import logging

from app.models.base import BaseModelAdapter

logger = logging.getLogger(__name__)


class YOLOAdapter(BaseModelAdapter):
    def __init__(self, checkpoint_path, device="auto", num_classes=80,
                 class_mapping=None, conf=0.25, iou=0.45, input_size=640, **kwargs):
        super().__init__(checkpoint_path=checkpoint_path, device=device,
                         num_classes=num_classes, class_mapping=class_mapping)
        self.conf = conf
        self.iou = iou
        self.input_size = input_size

    def load_model(self) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "YOLOAdapter needs `ultralytics` (pip install ultralytics). "
                f"Import failed: {exc}"
            ) from exc
        self.model = YOLO(str(self.checkpoint_path))
        try:
            self.model.to(self.device)
        except Exception:
            logger.warning("Could not move YOLO model to %s, keeping default.", self.device)
        self.loaded = True

    def preprocess(self, image):
        import numpy as np

        arr = np.asarray(image)
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        return arr.astype(np.uint8) if arr.dtype != np.uint8 else arr

    def detect(self, image) -> list:
        """list of {bbox [x1,y1,x2,y2], class_id, class_name, confidence}."""
        import numpy as np

        if self.model is None:
            raise RuntimeError("YOLOAdapter.load_model() must run before detect().")
        results = self.model.predict(
            source=self.preprocess(image), conf=self.conf, iou=self.iou,
            imgsz=self.input_size, verbose=False,
        )
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return []
        xyxy = np.asarray(boxes.xyxy.cpu())
        cls = np.asarray(boxes.cls.cpu(), dtype=int)
        conf = np.asarray(boxes.conf.cpu())
        detections = []
        for x1, y1, x2, y2, c, s in zip(xyxy[:, 0], xyxy[:, 1], xyxy[:, 2], xyxy[:, 3], cls, conf):
            detections.append({
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "class_id": int(c),
                "class_name": self.class_mapping.get(int(c), str(int(c))),
                "confidence": float(s),
            })
        return detections

    def predict(self, image) -> dict:
        return {"detections": self.detect(image)}

    def postprocess(self, raw_output) -> dict:
        """detect() already returns original-image coordinates; pass through."""
        return raw_output