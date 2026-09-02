"""Detects optional acceleration backends without making them hard dependencies."""

import importlib.util
import os
import platform
import shutil
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Tuple


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def _package_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _ffmpeg_path() -> str | None:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def get_runtime_capabilities() -> Dict[str, Any]:
    torch_version = _package_version("torch")
    cuda_available = False
    cuda_version = None
    gpu_name = None
    if torch_version:
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
            cuda_version = torch.version.cuda
            if cuda_available:
                gpu_name = torch.cuda.get_device_name(0)
        except Exception:
            pass

    ort_version = _package_version("onnxruntime-gpu") or _package_version("onnxruntime")
    ort_providers = []
    if ort_version:
        try:
            import onnxruntime as ort

            ort_providers = ort.get_available_providers()
        except Exception:
            pass

    sam3_path = Path(os.getenv("SAM3_MODEL_PATH", WORKSPACE_ROOT / "models" / "sam3.pt"))
    osnet_path = Path(
        os.getenv("OSNET_MODEL_PATH", WORKSPACE_ROOT / "models" / "osnet_x0_25.onnx")
    )
    inference_url = os.getenv("INFERENCE_SERVICE_URL", "").strip()
    requested_backend = os.getenv("VISION_BACKEND", "auto").lower()
    onnx_path = Path(
        os.getenv("YOLO_ONNX_PATH", WORKSPACE_ROOT / "models" / "yolov8n.onnx")
    )
    engine_path = Path(
        os.getenv("YOLO_TENSORRT_PATH", WORKSPACE_ROOT / "models" / "yolov8n.engine")
    )
    sam3_enabled = os.getenv("ENABLE_SAM3", "0") == "1"
    osnet_enabled = os.getenv("ENABLE_OSNET", "0") == "1"
    osnet_allow_download = os.getenv("OSNET_ALLOW_DOWNLOAD", "0") == "1"
    ffmpeg_enabled = os.getenv("ENABLE_FFMPEG_NORMALIZATION", "0") == "1"
    torchreid_available = _module_available("torchreid")
    osnet_onnx_available = (
        osnet_path.suffix.lower() == ".onnx" and osnet_path.is_file() and bool(ort_version)
    )
    osnet_torch_available = (
        osnet_path.suffix.lower() != ".onnx"
        and osnet_path.is_file()
        and torchreid_available
    ) or (osnet_allow_download and torchreid_available)
    osnet_available = osnet_onnx_available or osnet_torch_available
    sam3_available = sam3_path.is_file() and _module_available("ultralytics")
    ffmpeg_path = _ffmpeg_path()
    tensorrt_available = (
        "TensorrtExecutionProvider" in ort_providers or _module_available("tensorrt")
    )
    if (
        requested_backend in {"auto", "tensorrt"}
        and engine_path.is_file()
        and tensorrt_available
        and cuda_available
    ):
        selected_backend = "tensorrt"
    elif requested_backend in {"auto", "onnx"} and onnx_path.is_file() and bool(ort_version):
        selected_backend = "onnx"
    else:
        selected_backend = "pytorch"

    components = {
        "python": {"available": True, "active": True, "version": platform.python_version()},
        "pytorch": {
            "available": bool(torch_version),
            "active": bool(torch_version),
            "version": torch_version,
        },
        "ultralytics_yolo": {
            "available": _module_available("ultralytics"),
            "active": _module_available("ultralytics"),
            "version": _package_version("ultralytics"),
        },
        "sam3": {
            "available": sam3_available,
            "active": sam3_enabled and sam3_available,
            "model_path": str(sam3_path),
        },
        "onnx": {
            "available": bool(ort_version),
            "active": selected_backend == "onnx"
            or (osnet_enabled and osnet_onnx_available),
            "version": ort_version,
            "providers": ort_providers,
        },
        "tensorrt": {
            "available": tensorrt_available,
            "active": selected_backend == "tensorrt"
            or (
                osnet_enabled
                and osnet_onnx_available
                and "TensorrtExecutionProvider" in ort_providers
            ),
        },
        "cuda": {
            "available": cuda_available,
            "active": cuda_available,
            "version": cuda_version,
            "device": gpu_name,
        },
        "opencv": {
            "available": _module_available("cv2"),
            "active": _module_available("cv2"),
            "version": _package_version("opencv-python"),
        },
        "deep_eiou": {"available": True, "active": True, "implementation": "native"},
        "osnet_reid": {
            "available": osnet_available,
            "active": osnet_enabled and osnet_available,
            "model_path": str(osnet_path),
        },
        "ocr": {
            "available": _module_available("easyocr"),
            "active": _module_available("easyocr"),
            "engine": "EasyOCR",
        },
        "homography": {"available": True, "active": True, "engine": "OpenCV"},
        "flask": {
            "available": _module_available("flask"),
            "active": False,
            "service_url": inference_url or None,
        },
        "javascript": {"available": True, "active": True, "engine": "Next.js/React"},
        "ffmpeg": {
            "available": bool(ffmpeg_path),
            "active": ffmpeg_enabled and bool(ffmpeg_path),
            "path": ffmpeg_path,
        },
    }

    return {
        "requested_backend": requested_backend,
        "selected_backend": selected_backend,
        "inference_mode": "remote" if inference_url else "local",
        "components": components,
    }


def resolve_yolo_runtime(default_model: str = "yolov8n.pt") -> Tuple[str, str, str]:
    """Returns model path, backend label and Ultralytics device selection."""
    requested = os.getenv("VISION_BACKEND", "auto").lower()
    capabilities = get_runtime_capabilities()["components"]
    pt_path = os.getenv("YOLO_MODEL_PATH", default_model)
    onnx_path = os.getenv("YOLO_ONNX_PATH", str(WORKSPACE_ROOT / "models" / "yolov8n.onnx"))
    engine_path = os.getenv(
        "YOLO_TENSORRT_PATH", str(WORKSPACE_ROOT / "models" / "yolov8n.engine")
    )

    if (
        requested in {"auto", "tensorrt"}
        and capabilities["tensorrt"]["available"]
        and capabilities["cuda"]["available"]
    ):
        if Path(engine_path).is_file():
            return engine_path, "tensorrt", "0"
    if requested in {"auto", "onnx"} and capabilities["onnx"]["available"]:
        if Path(onnx_path).is_file():
            return onnx_path, "onnx", "0" if capabilities["cuda"]["available"] else "cpu"

    device = "0" if capabilities["cuda"]["available"] else "cpu"
    return pt_path, "pytorch", device
