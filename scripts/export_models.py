"""Exports Ultralytics models to ONNX and TensorRT for Shuttle Flux."""

import argparse
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="yolov8n.pt", help="Source Ultralytics .pt model")
    parser.add_argument(
        "--format",
        choices=("onnx", "engine", "all"),
        default="all",
        help="Export target; engine requires an NVIDIA CUDA environment",
    )
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--dynamic", action="store_true")
    parser.add_argument("--half", action="store_true")
    parser.add_argument("--output-dir", default="models")
    return parser.parse_args()


def export(format_name: str, args: argparse.Namespace) -> Path:
    from ultralytics import YOLO

    if format_name == "engine":
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("TensorRT export requires a CUDA-enabled PyTorch installation")

    model = YOLO(args.model)
    exported = Path(
        model.export(
            format=format_name,
            imgsz=args.imgsz,
            batch=args.batch,
            dynamic=args.dynamic,
            half=args.half,
            simplify=format_name == "onnx",
            device=0 if format_name == "engine" else None,
        )
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / exported.name
    if exported.resolve() != destination.resolve():
        shutil.move(str(exported), destination)
    return destination


def main() -> None:
    args = parse_args()
    formats = ("onnx", "engine") if args.format == "all" else (args.format,)
    for format_name in formats:
        output = export(format_name, args)
        print(f"Exported {format_name}: {output.resolve()}")


if __name__ == "__main__":
    main()
