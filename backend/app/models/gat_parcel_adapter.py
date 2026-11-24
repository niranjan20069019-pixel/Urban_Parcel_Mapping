"""Graph Attention Network (GAT) adapter for parcel relationship modeling.

Represents parcels as nodes and spatial relationships as edges for future
graph-based parcel reasoning. Requires PyG (torch_geometric).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from app.models.base import BaseModelAdapter

logger = logging.getLogger(__name__)


class GATParcelAdapter(BaseModelAdapter):
    """Graph Attention Network for parcel topology/relationship reasoning.

    Nodes = parcels (features: area, perimeter, building count, confidence).
    Edges = adjacency, shared boundary, road separation.

    Fallback: returns empty graph when no checkpoint or PyG is available.
    """

    def __init__(self, checkpoint_path, device="auto", num_classes=2,
                 class_mapping=None, threshold=0.5, input_size=512, **kwargs):
        super().__init__(checkpoint_path=checkpoint_path, device=device,
                         num_classes=num_classes, class_mapping=class_mapping)
        self._fallback_mode = True
        self._model = None

    def load_model(self) -> None:
        path = Path(self.checkpoint_path)
        try:
            import torch_geometric  # noqa: F401
        except ImportError:
            logger.warning(
                "torch_geometric not installed — GAT parcel adapter in fallback mode. "
                "Install with: pip install torch_geometric"
            )
            self._fallback_mode = True
            self.loaded = True
            return

        if not path.exists():
            logger.warning(
                "GAT checkpoint not found at %s — using adjacency-based fallback.",
                path,
            )
            self._fallback_mode = True
            self.loaded = True
            return

        try:
            import torch
            self._model = torch.jit.load(str(path), map_location=self.device)
            self._model.eval()
            self._fallback_mode = False
            self.loaded = True
            logger.info("Loaded GAT parcel model from %s", path)
        except Exception as exc:
            logger.warning("Failed to load GAT model: %s — using fallback.", exc)
            self._fallback_mode = True
            self.loaded = True

    def preprocess(self, image):
        """Input is a parcel graph dict, not an image."""
        return image

    def predict(self, image) -> dict:
        """image is a dict with parcel_features, edge_index, edge_attr."""
        if isinstance(image, dict):
            graph = image
        else:
            graph = {}

        if self._fallback_mode:
            return self._adjacency_fallback(graph)

        import torch
        x = torch.tensor(graph.get("parcel_features", []), dtype=torch.float32)
        edge_index = torch.tensor(graph.get("edge_index", [[], []]), dtype=torch.long)
        with torch.inference_mode():
            out = self._model(x, edge_index)
        if hasattr(out, "cpu"):
            out = out.cpu().numpy()
        return {"node_scores": np.asarray(out), "model": "gat"}

    def _adjacency_fallback(self, graph: dict) -> dict:
        features = graph.get("parcel_features", [])
        n = len(features) if features else 0
        return {
            "node_scores": np.ones(n, dtype=np.float32) * 0.5,
            "model": "adjacency_fallback",
            "message": "No GAT model loaded. Using uniform scores.",
        }

    def postprocess(self, raw_output) -> dict:
        if isinstance(raw_output, dict):
            return raw_output
        return {"node_scores": np.asarray(raw_output)}
