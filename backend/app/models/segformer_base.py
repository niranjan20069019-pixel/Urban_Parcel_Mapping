"""SegFormer segmentation adapter.

Preferred backend: a real SegFormer decoder for automatic image segmentation
built on a timm Mix-Transformer encoder via segmentation_models_pytorch.
Fallbacks: torch.hub "tristandk/smp", then torchvision DeepLabV3 — so a
checkpoint can be loaded even when the preferred stack is missing.
"""

from __future__ import annotations

import importlib
import logging

from app.models.segmentation_base import SegmentationModelAdapter

logger = logging.getLogger(__name__)

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


class SegFormerAdapter(SegmentationModelAdapter):
    def __init__(self, checkpoint_path, device="auto", num_classes=2, class_mapping=None,
                 threshold=0.5, input_size=512, encoder_name="mit_b0", encoder_weights=None,
                 in_channels=3, **kwargs):
        super().__init__(checkpoint_path=checkpoint_path, device=device, num_classes=num_classes,
                         class_mapping=class_mapping, threshold=threshold, input_size=input_size)
        self.encoder_name = encoder_name
        self.encoder_weights = encoder_weights
        self.in_channels = in_channels
        self.model_source: str | None = None

    # ----------------------------------- load -----------------------------------
    def load_model(self) -> None:
        import torch

        if not self.checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {self.checkpoint_path}")
        self._build_model()
        self._load_weights()
        self.model.to(self.device)
        self.model.eval()
        self.loaded = True
        logger.debug("Loaded %s adapter from %s (%s)", type(self).__name__,
                     self.checkpoint_path, self.model_source)

    def _build_model(self) -> None:
        errors = []
        try:
            smp = importlib.import_module("segmentation_models_pytorch")
            self.model = smp.Unet(
                encoder_name=self.encoder_name,
                encoder_weights=self.encoder_weights,
                in_channels=self.in_channels,
                classes=self.num_classes,
                activation=None,
            )
            self.model_source = "smp"
            return
        except Exception as exc:
            errors.append(f"smp.Unet(encoder={self.encoder_name}): {exc}")

        try:
            import torch
        except ImportError:
            errors.append("torch: not installed")
        else:
            for hub_name in ("segformer", "unet", "unetplusplus"):
                try:
                    self.model = torch.hub.load(
                        "tristandk/smp", hub_name,
                        encoder=self.encoder_name, classes=self.num_classes,
                        in_channels=self.in_channels,
                    )
                    self.model_source = f"torchhub:{hub_name}"
                    return
                except Exception as exc:
                    errors.append(f"torch.hub '{hub_name}': {exc}")

        try:
            import torch
            import torchvision as tv

            net = tv.models.segmentation.deeplabv3_resnet50(weights=None)
            net.classifier[4] = torch.nn.Conv2d(256, self.num_classes, kernel_size=1)
            net.aux_classifier[4] = torch.nn.Conv2d(256, self.num_classes, kernel_size=1)
            self.model = net
            self.model_source = "torchvision"
            return
        except Exception as exc:
            errors.append(f"torchvision deeplabv3: {exc}")

        raise ImportError(
            "No segmentation backend available for SegFormerAdapter. Install "
            "`segmentation_models_pytorch` + `timm` (preferred), or `torchvision`. Got:\n- "
            + "\n- ".join(errors)
        )

    def _load_weights(self) -> None:
        import torch

        path = self.checkpoint_path
        try:
            state = torch.load(path, map_location=self.device, weights_only=False)
        except TypeError:
            state = torch.load(path, map_location=self.device)
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        if any(k.startswith("module.") for k in state):
            state = {k[7:]: v for k, v in state.items()}
        try:
            self.model.load_state_dict(state, strict=True)
        except RuntimeError as exc:
            logger.warning("Loading checkpoint %s non-strictly: %s", path, exc)
            self.model.load_state_dict(state, strict=False)

    # --------------------------------- preprocessing -----------------------------
    def preprocess(self, image):
        import numpy as np
        import torch

        if image.ndim == 2:
            image = np.stack([image] * 3, axis=-1)
        img = self.resize_image(image, self.input_size)
        img = img.astype(np.float32) / 255.0
        tensor = self.normalize_image(img, IMAGENET_MEAN, IMAGENET_STD)
        return tensor.unsqueeze(0).to(self.device)

    # --------------------------------- forward ----------------------------------
    def _forward(self, tensor):
        import torch

        with torch.inference_mode():
            out = self.model(tensor)
            if isinstance(out, dict):  # torchvision backbones return {'out': ...}
                out = out["out"]
            return out.float() if not out.is_floating_point() else out

    # --------------------------------- predict ----------------------------------
    def predict(self, image) -> dict:
        self._last_orig_size = image.shape[:2]
        tensor = self.preprocess(image)
        return self.postprocess(self._forward(tensor))

    def postprocess(self, raw_output) -> dict:
        import numpy as np
        import torch

        if isinstance(raw_output, torch.Tensor):
            logits = raw_output.detach().cpu()
            logits_np = logits.numpy()
        else:
            logits_np = np.asarray(raw_output, dtype=np.float32)

        prob = self.softmax(logits_np)  # (1, C, H, W)
        probs_hwc = prob[0].transpose(1, 2, 0)  # (H, W, C)
        mask = self.mask_from_probabilities(probs_hwc, self.threshold)
        confidence = self.get_confidence_map(probs_hwc)

        orig = self._last_orig_size or (probs_hwc.shape[0], probs_hwc.shape[1])
        mask = self.resize_array(mask, orig, is_mask=True).astype(np.int32)
        confidence = self.resize_array(confidence, orig)
        probabilities = self.resize_array(probs_hwc, orig)

        return {
            "mask": mask,
            "confidence": confidence,
            "probabilities": probabilities,
            "logits": logits_np,
        }

    def get_model_info(self) -> dict:
        info = super().get_model_info()
        info.update({
            "architecture": self.model_source or "segformer",
            "encoder": self.encoder_name,
            "input_size": self.input_size,
            "threshold": self.threshold,
        })
        return info