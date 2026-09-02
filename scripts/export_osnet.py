"""Exports an OSNet ReID feature extractor to ONNX."""

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", default="osnet_x0_25")
    parser.add_argument("--weights", help="Optional Torchreid checkpoint")
    parser.add_argument("--output", default="models/osnet_x0_25.onnx")
    parser.add_argument("--opset", type=int, default=17)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        import torch
        import torchreid
    except ImportError as exc:
        raise SystemExit(
            "Install apps/worker/requirements-gpu.txt before exporting OSNet"
        ) from exc

    model = torchreid.models.build_model(
        name=args.arch,
        num_classes=1000,
        loss="softmax",
        pretrained=args.weights is None,
        use_gpu=False,
    )
    if args.weights:
        torchreid.utils.load_pretrained_weights(model, args.weights)
    model.eval()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sample = torch.randn(1, 3, 256, 128)
    torch.onnx.export(
        model,
        sample,
        str(output),
        input_names=["images"],
        output_names=["embeddings"],
        dynamic_axes={"images": {0: "batch"}, "embeddings": {0: "batch"}},
        opset_version=args.opset,
        do_constant_folding=True,
    )
    print(f"Exported OSNet ONNX: {output.resolve()}")


if __name__ == "__main__":
    main()
