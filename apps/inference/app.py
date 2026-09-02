"""Flask service that keeps vision models warm outside the FastAPI process."""

import os
import sys
from typing import Any

import cv2
import numpy as np
from flask import Flask, jsonify, request


WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from ml.runtime.capabilities import get_runtime_capabilities
from pipelines.detect import DetectionPipeline


app = Flask(__name__)
pipeline: DetectionPipeline | None = None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _pipeline() -> DetectionPipeline:
    global pipeline
    if pipeline is None:
        pipeline = DetectionPipeline(use_remote=False)
    return pipeline


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "healthy", "service": "shuttle-flux-inference"})


@app.get("/v1/capabilities")
def capabilities() -> Any:
    runtime = get_runtime_capabilities()
    runtime["components"]["flask"]["active"] = True
    return jsonify(_json_safe(runtime))


@app.post("/v1/detect")
def detect() -> Any:
    image_file = request.files.get("image")
    if image_file is None:
        return jsonify({"error": "multipart field 'image' is required"}), 400

    encoded = np.frombuffer(image_file.read(), dtype=np.uint8)
    frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"error": "image could not be decoded"}), 400

    result = _pipeline().run_frame(frame)
    return jsonify(_json_safe(result))


if __name__ == "__main__":
    app.run(
        host=os.getenv("INFERENCE_HOST", "0.0.0.0"),
        port=int(os.getenv("INFERENCE_PORT", "5001")),
        threaded=False,
    )
