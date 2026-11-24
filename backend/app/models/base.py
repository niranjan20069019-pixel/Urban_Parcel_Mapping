"""Base model interface shared by every adapter in the framework."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseModelAdapter(ABC):
    """Base class for all model adapters.

    Heavy dependencies (torch, numpy, ...) are imported lazily inside the
    methods so that importing this package never fails on a bare box.
    """

    def __init__(self, checkpoint_path, device="auto", num_classes=2, class_mapping=None):
        self.checkpoint_path = Path(checkpoint_path)
        self.device = self._resolve_device(device)
        self.num_classes = num_classes
        self.class_mapping = class_mapping or {}
        self.model = None
        self.loaded = False

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    @abstractmethod
    def load_model(self) -> None:
        """Load the network weights and switch the model to eval mode."""

    @abstractmethod
    def preprocess(self, image) -> "torch.Tensor":
        """Turn a raw HWC image into a model-ready tensor."""

    @abstractmethod
    def predict(self, image) -> dict:
        """Run inference. Returns a dict with at least mask/confidence."""

    @abstractmethod
    def postprocess(self, raw_output) -> dict:
        """Convert raw model output into the public prediction dict."""

    def unload(self) -> None:
        """Release the model from memory and free GPU memory if present."""
        self.model = None
        self.loaded = False
        try:
            import torch

            if self.device == "cuda":
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def get_model_info(self) -> dict:
        return {
            "name": type(self).__name__,
            "checkpoint_path": str(self.checkpoint_path),
            "device": self.device,
            "num_classes": self.num_classes,
            "class_mapping": self.class_mapping,
            "loaded": self.loaded,
            "model": str(self.model) if self.model is not None else None,
        }

    def validate_checkpoint(self) -> bool:
        """True when the checkpoint exists, is non-empty and torch can read it."""
        if not self.checkpoint_path.exists() or self.checkpoint_path.stat().st_size == 0:
            return False
        try:
            import torch

            try:
                data = torch.load(self.checkpoint_path, map_location="cpu", weights_only=False)
            except TypeError:
                data = torch.load(self.checkpoint_path, map_location="cpu")
            return data is not None
        except Exception:
            return False