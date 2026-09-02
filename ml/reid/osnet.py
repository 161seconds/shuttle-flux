"""OSNet appearance embeddings for stable player identities."""

import os
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np

from ml.runtime.onnx_session import create_onnx_session


class OSNetEmbedder:
    def __init__(self, model_path: str | None = None, device: str = "cpu"):
        workspace_root = Path(__file__).resolve().parents[2]
        self.model_path = Path(
            model_path
            or os.getenv(
                "OSNET_MODEL_PATH", workspace_root / "models" / "osnet_x0_25.onnx"
            )
        )
        self.device = "cuda" if device != "cpu" else "cpu"
        self.enabled = os.getenv("ENABLE_OSNET", "0") == "1"
        self.backend: str | None = None
        self.session = None
        self.extractor = None

    def _load(self) -> bool:
        if not self.enabled:
            return False
        if self.session is not None or self.extractor is not None:
            return True

        try:
            if self.model_path.suffix.lower() == ".onnx" and self.model_path.is_file():
                self.session, providers = create_onnx_session(str(self.model_path))
                self.backend = providers[0]
                print(f"[OSNet] Loaded ONNX model with {self.backend}")
                return True

            if self.model_path.is_file() or os.getenv("OSNET_ALLOW_DOWNLOAD", "0") == "1":
                from torchreid.utils import FeatureExtractor

                self.extractor = FeatureExtractor(
                    model_name=os.getenv("OSNET_ARCH", "osnet_x0_25"),
                    model_path=str(self.model_path) if self.model_path.is_file() else "",
                    device=self.device,
                )
                self.backend = "pytorch"
                print(f"[OSNet] Loaded Torchreid model on {self.device}")
                return True
        except Exception as exc:
            print(f"[OSNet] Disabled after model load failure: {exc}")

        self.enabled = False
        return False

    @staticmethod
    def _crop(frame: np.ndarray, bbox: List[float]) -> np.ndarray | None:
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = [int(round(value)) for value in bbox]
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]

    @staticmethod
    def _normalize(features: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(features, axis=1, keepdims=True)
        return features / np.maximum(norms, 1e-12)

    def _extract_onnx(self, crops: List[np.ndarray]) -> np.ndarray:
        batch = []
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        for crop in crops:
            rgb = cv2.cvtColor(cv2.resize(crop, (128, 256)), cv2.COLOR_BGR2RGB)
            normalized = (rgb.astype(np.float32) / 255.0 - mean) / std
            batch.append(np.transpose(normalized, (2, 0, 1)))
        inputs = np.stack(batch, axis=0)
        input_meta = self.session.get_inputs()[0]
        input_name = input_meta.name
        fixed_batch = input_meta.shape[0] if input_meta.shape else None
        if fixed_batch == 1 and len(inputs) > 1:
            outputs = np.concatenate(
                [self.session.run(None, {input_name: item[None, ...]})[0] for item in inputs],
                axis=0,
            )
        else:
            outputs = self.session.run(None, {input_name: inputs})[0]
        return self._normalize(np.asarray(outputs, dtype=np.float32).reshape(len(crops), -1))

    def attach_embeddings(
        self, frame: np.ndarray, detections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not detections or not self._load():
            return detections

        valid_indices = []
        crops = []
        for index, detection in enumerate(detections):
            crop = self._crop(frame, detection["bbox"])
            if crop is not None:
                valid_indices.append(index)
                crops.append(crop)
        if not crops:
            return detections

        try:
            if self.session is not None:
                embeddings = self._extract_onnx(crops)
            else:
                rgb_crops = [cv2.cvtColor(crop, cv2.COLOR_BGR2RGB) for crop in crops]
                features = self.extractor(rgb_crops)
                if hasattr(features, "detach"):
                    features = features.detach().cpu().numpy()
                embeddings = self._normalize(np.asarray(features, dtype=np.float32))
        except Exception as exc:
            print(f"[OSNet] Embedding extraction failed: {exc}")
            return detections

        enriched = [dict(detection) for detection in detections]
        for index, embedding in zip(valid_indices, embeddings):
            enriched[index]["embedding"] = embedding.astype(np.float32)
            enriched[index]["reid_source"] = f"osnet:{self.backend}"
        return enriched
