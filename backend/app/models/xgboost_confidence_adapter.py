"""XGBoost confidence-calibration adapter for segmentation outputs.

Learns a mapping from per-pixel/per-parcel features to prediction quality.
Requires a trained XGBoost model; falls back to rule-based scoring.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from app.models.base import BaseModelAdapter

logger = logging.getLogger(__name__)


class XGBoostConfidenceAdapter(BaseModelAdapter):
    """Gradient-boosted confidence estimator on top of segmentation predictions.

    Input features: AI confidence, mask area, boundary evidence, topology flags.
    Output: review probability (0-1).

    Fallback: returns a constant 0.5 when no model is loaded.
    """

    def __init__(self, checkpoint_path, device="auto", num_classes=2,
                 class_mapping=None, threshold=0.5, input_size=512, **kwargs):
        super().__init__(checkpoint_path=checkpoint_path, device=device,
                         num_classes=num_classes, class_mapping=class_mapping)
        self._bst = None
        self._fallback_mode = True

    def load_model(self) -> None:
        path = Path(self.checkpoint_path)
        if not path.exists():
            logger.warning(
                "XGBoost checkpoint not found at %s — confidence estimation will use "
                "rule-based fallback. Train an XGBoost model and place it at the "
                "configured path.",
                path,
            )
            self._fallback_mode = True
            self.loaded = True
            return

        try:
            import xgboost as xgb
            self._bst = xgb.Booster()
            self._bst.load_model(str(path))
            self._fallback_mode = False
            self.loaded = True
            logger.info("Loaded XGBoost confidence model from %s", path)
        except Exception as exc:
            logger.warning("Failed to load XGBoost model: %s — using rule-based fallback.", exc)
            self._fallback_mode = True
            self.loaded = True

    def preprocess(self, image):
        """Features are extracted from segmentation outputs, not raw images."""
        return image

    def predict(self, image) -> dict:
        """image is expected to be a feature dict from the pipeline, not a raw image.

        Expected keys: ai_confidence, mask_area, boundary_score, topology_valid.
        """
        if isinstance(image, dict):
            features = image
        else:
            features = {}

        if self._fallback_mode:
            return self._rule_based(features)

        import xgboost as xgb
        feature_names = [
            "ai_confidence", "mask_area", "boundary_score",
            "topology_valid", "gnss_agreement", "area_plausibility",
        ]
        vals = [float(features.get(k, 0.5)) for k in feature_names]
        dm = xgb.DMatrix(np.array([vals]), feature_names=feature_names)
        score = float(self._bst.predict(dm)[0])
        return {
            "review_probability": score,
            "features": dict(zip(feature_names, vals)),
            "model": "xgboost",
        }

    def _rule_based(self, features: dict) -> dict:
        ai_conf = features.get("ai_confidence", 0.5)
        topo = features.get("topology_valid", 1.0)
        review_prob = max(0.0, 1.0 - ai_conf * 0.6 - topo * 0.4)
        return {
            "review_probability": review_prob,
            "features": features,
            "model": "rule_based_fallback",
        }

    def postprocess(self, raw_output) -> dict:
        if isinstance(raw_output, dict):
            return raw_output
        return {"review_probability": 0.5, "model": "unknown"}
