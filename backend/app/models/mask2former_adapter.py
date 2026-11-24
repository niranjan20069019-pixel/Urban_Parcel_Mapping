"""Optional Mask2Former adapter (HuggingFace transformers backend).

Drop-in for the SegFormer adapters: load_model/preprocess/predict/postprocess
with the canonical composite-mask decoding from the Mask2Former paper.
"""

from __future__ import annotations

from app.models.segmentation_base import SegmentationModelAdapter


class Mask2FormerAdapter(SegmentationModelAdapter):
    def __init__(self, checkpoint_path, device="auto", num_classes=150,
                 class_mapping=None, input_size=512, **kwargs):
        super().__init__(checkpoint_path=checkpoint_path, device=device,
                         num_classes=num_classes, class_mapping=class_mapping,
                         threshold=kwargs.pop("threshold", 0.0),
                         input_size=input_size)
        self.processor = None

    def load_model(self) -> None:
        try:
            import torch
            from transformers import Mask2FormerForUniversalSegmentation
            from transformers import Mask2FormerImageProcessor
        except ImportError as exc:
            raise RuntimeError(
                "Mask2FormerAdapter needs `transformers` (pip install transformers). "
                f"Import failed: {exc}"
            ) from exc

        path = str(self.checkpoint_path)
        try:
            self.model = Mask2FormerForUniversalSegmentation.from_pretrained(path)
            self.processor = Mask2FormerImageProcessor.from_pretrained(path)
        except Exception as exc:
            raise RuntimeError(
                "Failed to load Mask2Former config/weights. Pass a local directory "
                f"containing config.json/.bin, not a bare .pth file. Got: {exc}"
            ) from exc
        self.model.to(self.device)
        self.model.eval()
        self.loaded = True

    def preprocess(self, image):
        import torch

        arr = np.asarray(image)
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        return torch.from_numpy(arr.astype(np.float32) / 255.0)

    def _forward(self, tensor):
        import torch

        with torch.inference_mode():
            return self.model(**tensor)  # preprocessed processor batch dict

    def _postprocess_composite(self, outputs) -> tuple:
        """Composite mask (covers labels across queries) + per-label certainty maps."""
        import numpy as np
        import torch

        mask_logits = torch.sigmoid(outputs.masks_queries_logits)[0]  # (Q,H,W)
        class_logits = outputs.class_queries_logits[0]  # (Q,num_labels)
        labels = class_logits.argmax(dim=-1)  # (Q,)

        chosen = mask_logits.argmax(dim=0)  # best query per pixel
        mask = labels[chosen].cpu().numpy().astype(np.int32)
        confidence = mask_logits.max(dim=0).values.cpu().numpy()

        probs = torch.zeros((self.num_classes, *mask.shape), dtype=mask_logits.dtype)
        for q in range(mask_logits.shape[0]):
            probs[labels[q]] = torch.maximum(
                probs[labels[q]], mask_logits[q]
            )
        probs = probs.permute(1, 2, 0).cpu().numpy()
        return mask, confidence, probs

    def predict(self, image) -> dict:
        self._last_orig_size = image.shape[:2]
        inputs = self.processor(images=self.preprocess(image).numpy(), return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        return self.postprocess(self._forward(inputs))

    def postprocess(self, raw_output) -> dict:
        mask, confidence, probs = self._postprocess_composite(raw_output)
        orig = self._last_orig_size or (mask.shape[0], mask.shape[1])
        return {
            "mask": self.resize_array(mask, orig, is_mask=True).astype(np.int32),
            "confidence": self.resize_array(confidence, orig),
            "probabilities": self.resize_array(probs, orig),
            "logits": None,
        }