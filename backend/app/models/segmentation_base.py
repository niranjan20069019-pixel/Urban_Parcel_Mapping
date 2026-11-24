"""Shared segmentation utilities (image/resize/normalize/softmax batched) and the model registry."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field

from app.models.base import BaseModelAdapter

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    enabled: bool = True
    architecture: str = "segformer"
    checkpoint: str | None = None
    device: str = "auto"
    num_classes: int = 2
    class_mapping: dict[int, str] | None = None
    threshold: float = 0.5
    input_size: int = 512


@dataclass
class ModelRegistryConfig:
    models: dict[str, ModelConfig] = field(default_factory=dict)


class ModelRegistry:
    """Holds adapter classes + configs, instantiates them lazily, adapter-keyed by name."""

    def __init__(self, config: ModelRegistryConfig | None = None):
        self.config = config
        self._models: dict[str, tuple[type, ModelConfig]] = {}
        self._instances: dict[str, BaseModelAdapter] = {}

    def register(self, name: str, adapter_class: type, config: ModelConfig) -> None:
        self._models[name] = (adapter_class, config)
        self._instances.pop(name, None)

    def get(self, name: str) -> BaseModelAdapter:
        if name in self._instances:
            return self._instances[name]
        if name not in self._models:
            raise KeyError(f"Model '{name}' is not registered. Available: {list(self._models)}")
        adapter_class, config = self._models[name]
        instance = adapter_class(**self._adapter_kwargs(adapter_class, config))
        self._instances[name] = instance
        return instance

    @staticmethod
    def _adapter_kwargs(adapter_class: type, config: ModelConfig) -> dict:
        params = inspect.signature(adapter_class.__init__).parameters
        available = {
            p for p, v in params.items()
            if v.kind in (v.POSITIONAL_OR_KEYWORD, v.KEYWORD_ONLY)
        }
        mapping = {
            "checkpoint_path": config.checkpoint,
            "device": config.device,
            "num_classes": config.num_classes,
            "class_mapping": config.class_mapping,
            "threshold": config.threshold,
            "input_size": config.input_size,
        }
        return {k: v for k, v in mapping.items() if k in available and v is not None}

    def list_models(self) -> dict:
        out = {}
        for name, (_, cfg) in self._models.items():
            loaded = False
            if name in self._instances:
                loaded = self._instances[name].loaded
            out[name] = {
                "name": name,
                "architecture": cfg.architecture,
                "enabled": cfg.enabled,
                "checkpoint": str(cfg.checkpoint) if cfg.checkpoint else None,
                "device": cfg.device,
                "num_classes": cfg.num_classes,
                "class_mapping": cfg.class_mapping,
                "threshold": cfg.threshold,
                "input_size": cfg.input_size,
                "loaded": loaded,
            }
        return out

    def load_all(self, config: ModelRegistryConfig | None = None, model_classes: dict | None = None) -> int:
        """Register + instantiate + load every enabled model. Returns the loaded count."""
        if config is not None:
            self.config = config
        if self.config is None:
            raise ValueError("No ModelRegistryConfig provided to load_all().")
        classes = dict(self.default_model_classes())
        if model_classes:
            classes.update(model_classes)
        loaded = 0
        for name, cfg in self.config.models.items():
            if not cfg.enabled:
                continue
            try:
                self.register(name, classes[cfg.architecture], cfg)
                adapter = self.get(name)
                adapter.load_model()
                loaded += 1
            except Exception as exc:
                logger.warning("Failed to load model '%s' (%s): %s", name, cfg.architecture, exc)
        return loaded

    @staticmethod
    def default_model_classes() -> dict:
        from app.models.mask2former_adapter import Mask2FormerAdapter
        from app.models.segformer_base import SegFormerAdapter
        from app.models.segformer_boundary import SegFormerBoundary
        from app.models.segformer_building import SegFormerBuilding
        from app.models.segformer_landuse import SegFormerLanduse
        from app.models.segformer_road import SegFormerRoad
        from app.models.yolo_adapter import YOLOAdapter

        return {
            "segformer": SegFormerAdapter,
            "segformer_building": SegFormerBuilding,
            "segformer_road": SegFormerRoad,
            "segformer_landuse": SegFormerLanduse,
            "segformer_boundary": SegFormerBoundary,
            "mask2former": Mask2FormerAdapter,
            "yolo": YOLOAdapter,
        }


class SegmentationModelAdapter(BaseModelAdapter):
    """Shared plumbing for pixel-segmentation adapters (predicates, resize, softmax, batch)."""

    def __init__(self, checkpoint_path, device="auto", num_classes=2, class_mapping=None,
                 threshold=0.5, input_size=512, **kwargs):
        super().__init__(checkpoint_path=checkpoint_path, device=device,
                         num_classes=num_classes, class_mapping=class_mapping)
        self.threshold = threshold
        self.input_size = input_size
        self._last_orig_size: tuple[int, int] | None = None

    # ------------------------------ image helpers ------------------------------
    @staticmethod
    def _resize_nearest_fallback(array, dst_h: int, dst_w: int):
        import numpy as np

        src_h, src_w = array.shape[:2]
        ys = np.linspace(0, src_h - 1, dst_h).astype(int)
        xs = np.linspace(0, src_w - 1, dst_w).astype(int)
        if array.ndim == 2:
            return array[np.ix_(ys, xs)]
        return array[np.ix_(ys, xs, np.arange(array.shape[2]))]

    @classmethod
    def resize_array(cls, array, target_size, interpolation=None, is_mask=False):
        """Resize any 2D/3D array to (height, width) == target_size."""
        import numpy as np

        arr = np.asarray(array)
        if isinstance(target_size, int):
            dst_h = dst_w = target_size
        else:
            dst_h, dst_w = int(target_size[0]), int(target_size[1])
        try:
            import cv2

            if interpolation is None:
                if is_mask:
                    interpolation = cv2.INTER_NEAREST
                elif arr.dtype == np.uint8:
                    interpolation = cv2.INTER_AREA
                else:
                    interpolation = cv2.INTER_LINEAR
            return cv2.resize(arr, (dst_w, dst_h), interpolation=interpolation)
        except ImportError:
            if arr.ndim == 2:
                from PIL import Image

                mode = Image.NEAREST if is_mask else Image.BILINEAR
                return np.asarray(Image.fromarray(arr).resize((dst_w, dst_h), mode))
            return cls._resize_nearest_fallback(arr, dst_h, dst_w)

    @classmethod
    def resize_image(cls, image, target_size):
        return cls.resize_array(image, target_size)

    @staticmethod
    def normalize_image(image, mean, std):
        """float [0,1] HWC array -> (3,H,W) tensor using per-channel mean/std."""
        import numpy as np
        import torch

        img = np.asarray(image, dtype=np.float32)
        mean = np.asarray(mean, dtype=np.float32).reshape(3, 1, 1)
        std = np.asarray(std, dtype=np.float32).reshape(3, 1, 1)
        hwc = img.transpose(2, 0, 1)
        return torch.from_numpy(np.ascontiguousarray((hwc - mean) / std))

    @staticmethod
    def skeletonize(mask):
        """Binary mask -> 1px skeleton. Requires scikit-image or opencv-contrib."""
        import numpy as np

        m = np.asarray(mask, dtype=np.uint8)
        try:
            from skimage.morphology import skeletonize as _skeletonize

            return _skeletonize(m > 0).astype(np.uint8)
        except ImportError:
            try:
                import cv2

                return cv2.ximgproc.thinning(m)
            except (ImportError, AttributeError):
                raise RuntimeError(
                    "skeletonize() needs scikit-image or opencv-contrib-python (cv2.ximgproc)."
                )

    # ---------------------------- probability helpers --------------------------
    @staticmethod
    def softmax(logits):
        """logits (B,C,H,W) or (C,H,W) tensor/array -> same-shaped numpy probabilities."""
        import numpy as np

        try:
            import torch

            is_tensor = isinstance(logits, torch.Tensor)
        except ImportError:
            is_tensor = False

        if is_tensor:
            axis = 1 if logits.dim() == 4 else 0
            return torch.softmax(logits, dim=axis).cpu().numpy()
        arr = np.asarray(logits, dtype=np.float32)
        axis = 1 if arr.ndim == 4 else 0
        e = np.exp(arr - arr.max(axis=axis, keepdims=True))
        return e / e.sum(axis=axis, keepdims=True)

    @staticmethod
    def mask_from_probabilities(probabilities, threshold=0.5) -> "np.ndarray":
        """(H,W,C) or (H,W) probabilities -> (H,W) int mask, low confidence -> background(0)."""
        import numpy as np

        p = np.asarray(probabilities)
        if p.ndim == 2:
            return (p >= threshold).astype(np.int32)
        if p.shape[-1] == 1:
            return (p[..., 0] >= threshold).astype(np.int32)
        max_p = p.max(axis=-1)
        cls = p.argmax(axis=-1)
        return np.where(max_p >= threshold, cls, 0).astype(np.int32)

    @staticmethod
    def get_confidence_map(probabilities) -> "np.ndarray":
        """(H,W,C) or (H,W) probabilities -> (H,W) max-class confidence."""
        import numpy as np

        p = np.asarray(probabilities)
        return p.max(axis=-1) if p.ndim == 3 else p

    # ------------------------------ batch execution ----------------------------
    def batch_inference(self, images) -> list:
        """Predict multiple HWC images in one forward pass."""
        import torch

        tensors = [self.preprocess(img) for img in images]
        batch = torch.cat(tensors, dim=0)
        outputs = self._forward(batch)
        results = []
        for i, img in enumerate(images):
            self._last_orig_size = img.shape[:2] if hasattr(img, "shape") else None
            results.append(self.postprocess(outputs[i: i + 1]))
        return results

    def _forward(self, tensor):
        raise NotImplementedError(f"{type(self).__name__} must implement _forward(tensor).")


registry = ModelRegistry()


if __name__ == "__main__":
    # Self-check for the registry (pure python, no numpy/torch needed).
    class _DemoSeg(SegmentationModelAdapter):
        def load_model(self):
            self.loaded = True

        def preprocess(self, image):
            return image

        def predict(self, image):
            return {"mask": 0}

        def postprocess(self, raw_output):
            return {"mask": 0}

    cfg = ModelRegistryConfig(models={
        "demo": ModelConfig(architecture="segformer_building", checkpoint="/tmp/fake.pth", threshold=0.6),
        "off": ModelConfig(architecture="segformer_road", enabled=False),
    })
    r = ModelRegistry()
    loaded = r.load_all(cfg, model_classes={"segformer_building": _DemoSeg})
    assert loaded == 1, loaded
    assert list(r.list_models()) == ["demo"]
    assert r.list_models()["demo"]["threshold"] == 0.6
    assert r.get("demo").loaded is True
    r.get("demo").unload()
    assert r.get("demo").loaded is False
    print(f"registry selftest OK: loaded={loaded}, models={list(r.list_models())}")