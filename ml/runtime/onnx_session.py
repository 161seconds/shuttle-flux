"""ONNX Runtime session factory with TensorRT/CUDA/CPU fallback."""

from pathlib import Path
from typing import Any, Dict, List, Tuple


def create_onnx_session(
    model_path: str,
    device_id: int = 0,
    fp16: bool = True,
    cache_dir: str = "storage/model_cache/tensorrt",
) -> Tuple[Any, List[str]]:
    import onnxruntime as ort

    available = set(ort.get_available_providers())
    providers: List[Any] = []
    provider_names: List[str] = []

    if "TensorrtExecutionProvider" in available:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        trt_options: Dict[str, Any] = {
            "device_id": device_id,
            "trt_engine_cache_enable": True,
            "trt_engine_cache_path": str(Path(cache_dir).resolve()),
            "trt_fp16_enable": fp16,
        }
        providers.append(("TensorrtExecutionProvider", trt_options))
        provider_names.append("TensorrtExecutionProvider")

    if "CUDAExecutionProvider" in available:
        providers.append(("CUDAExecutionProvider", {"device_id": device_id}))
        provider_names.append("CUDAExecutionProvider")

    providers.append("CPUExecutionProvider")
    provider_names.append("CPUExecutionProvider")

    session = ort.InferenceSession(model_path, providers=providers)
    return session, provider_names
