"""Test optional model adapters and the deterministic demo (mock) mode."""

import numpy as np
import pytest


def test_siamese_fallback_without_checkpoint(tmp_path):
    from app.models.siamese_change_adapter import SiameseChangeAdapter

    img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
    changed = (img * 0.5).astype(np.uint8)
    adapter = SiameseChangeAdapter(checkpoint_path=tmp_path / "missing.pth")
    adapter.load_model()
    assert adapter.loaded
    out = adapter.predict({"image_t0": img, "image_t1": changed})
    assert "mask" in out
    assert out["mask"].shape == (64, 64)


def test_xgboost_fallback_without_checkpoint(tmp_path):
    from app.models.xgboost_confidence_adapter import XGBoostConfidenceAdapter

    adapter = XGBoostConfidenceAdapter(checkpoint_path=tmp_path / "missing.model")
    adapter.load_model()
    out = adapter.predict({"ai_confidence": 0.9, "topology_valid": 1.0})
    assert 0.0 <= out["review_probability"] <= 1.0
    assert out["model"] == "rule_based_fallback"


def test_gat_fallback(tmp_path):
    from app.models.gat_parcel_adapter import GATParcelAdapter

    adapter = GATParcelAdapter(checkpoint_path=tmp_path / "missing.pt")
    adapter.load_model()
    out = adapter.predict({"parcel_features": [[1.0], [2.0]], "edge_index": [[0], [1]]})
    assert out["node_scores"].shape == (2,)


def test_change_transformer_fallback(tmp_path):
    from app.models.change_transformer_adapter import ChangeTransformerAdapter

    a = np.zeros((64, 64, 3), dtype=np.uint8)
    b = np.zeros((64, 64, 3), dtype=np.uint8)
    b[:, :32] = 255
    adapter = ChangeTransformerAdapter(checkpoint_path=tmp_path / "missing.pth")
    adapter.load_model()
    out = adapter.predict({"image_t0": a, "image_t1": b})
    assert "mask" in out
    assert 0 < out["mask"].sum() < 64 * 64


def test_demo_mock_mask_label():
    from app.core.mock import MOCK_LABEL, build_mock_mask

    assert MOCK_LABEL == "DEVELOPMENT MOCK — NOT AI PREDICTION"
    img = np.zeros((128, 128, 3), dtype=np.uint8)
    for model in ("building", "road", "landuse", "boundary"):
        out = build_mock_mask(img, model, seed=0)
        assert out["is_mock"] is True
        assert out["mask"].shape == (128, 128)
        assert out["mask"].max() > 0
        assert out["confidence"].shape == (128, 128)


def test_yolo_requires_ultralytics(tmp_path):
    from app.models.yolo_adapter import YOLOAdapter

    adapter = YOLOAdapter(checkpoint_path=tmp_path / "yolo.pt")
    with pytest.raises(RuntimeError):
        adapter.load_model()  # ultralytics not installed in base env