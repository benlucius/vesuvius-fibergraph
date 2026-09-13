from __future__ import annotations

import argparse
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .metrics import evaluate_predictions
from .nml import read_nml
from .workflows import (
    export_vc3d_seed_bundle_from_manifest,
    prepare_seed_manifest_from_manifest,
    prepare_seed_manifest_from_npz,
    read_prediction_json,
    write_json_document,
)


def _package_version() -> str:
    try:
        return version("fibergraph")
    except PackageNotFoundError:
        return "0+local"


def _add_seed_quality_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--min-branch-margin", type=float, default=0.10)
    parser.add_argument("--nms-radius", type=int, default=2)
    parser.add_argument("--min-distance", type=float, default=12.0)
    parser.add_argument("--max-seeds", type=int)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fibergraph",
        description="Precision-first global papyrus-fiber assembly and Villa/VC3D seed tooling",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_package_version()}")
    sub = parser.add_subparsers(dest="command", required=True)

    evaluate = sub.add_parser("eval", help="evaluate traces against a ScrollPrize/WebKnossos NML")
    evaluate.add_argument("gt_nml", type=Path)
    evaluate.add_argument("pred_json", type=Path)
    evaluate.add_argument("--tolerance", type=float, default=3.0)
    evaluate.add_argument("--spacing", type=float, default=1.0)

    seeds = sub.add_parser("seeds", help="prepare conservative seed requests from Villa Fiber3D predictions")
    seeds_sub = seeds.add_subparsers(dest="seed_source", required=True)

    npz = seeds_sub.add_parser("npz", help="read option_NNN_presence/nx/ny arrays from an NPZ crop")
    npz.add_argument("predictions_npz", type=Path)
    npz.add_argument("output_json", type=Path)
    npz.add_argument("--fiber-manifest", type=Path)
    npz.add_argument("--prediction-to-base-scale", type=float)
    npz.add_argument(
        "--origin-zyx", nargs=3, type=float, default=(0.0, 0.0, 0.0),
        metavar=("Z", "Y", "X"),
        help="crop origin in persisted prediction-grid voxels, before base scaling",
    )
    _add_seed_quality_args(npz)

    manifest = seeds_sub.add_parser(
        "manifest", help="read persisted option channels directly from a local Villa .lasagna.json"
    )
    manifest.add_argument("fiber_manifest", type=Path)
    manifest.add_argument("output_json", type=Path)
    manifest.add_argument(
        "--crop-zyx", nargs=6, type=int,
        metavar=("Z0", "Z1", "Y0", "Y1", "X0", "X1"),
        help="optional crop in persisted prediction-array coordinates",
    )
    _add_seed_quality_args(manifest)

    vc3d = sub.add_parser(
        "vc3d-export", help="convert base-coordinate FiberGraph seed requests to seed-only VC3D v3 JSON files"
    )
    vc3d.add_argument("seed_manifest", type=Path)
    vc3d.add_argument("output_dir", type=Path)
    vc3d.add_argument("--generation", type=int, default=0)
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "eval":
            metrics = evaluate_predictions(
                read_nml(args.gt_nml),
                read_prediction_json(args.pred_json),
                tolerance=args.tolerance,
                spacing=args.spacing,
            )
            print(json.dumps(metrics.to_dict(), indent=2, sort_keys=True))
            return 0

        if args.command == "seeds" and args.seed_source == "npz":
            document = prepare_seed_manifest_from_npz(
                args.predictions_npz,
                fiber_manifest=args.fiber_manifest,
                prediction_to_base_scale=args.prediction_to_base_scale,
                origin_zyx=tuple(args.origin_zyx),
                threshold=args.threshold,
                min_branch_margin=args.min_branch_margin,
                nms_radius=args.nms_radius,
                min_distance=args.min_distance,
                max_seeds=args.max_seeds,
            )
            write_json_document(args.output_json, document)
            print(
                f"wrote {len(document['requests'])} seed requests to {args.output_json} "
                f"({document['coordinate_space']})"
            )
            return 0

        if args.command == "seeds" and args.seed_source == "manifest":
            document = prepare_seed_manifest_from_manifest(
                args.fiber_manifest,
                crop_zyx=None if args.crop_zyx is None else tuple(args.crop_zyx),
                threshold=args.threshold,
                min_branch_margin=args.min_branch_margin,
                nms_radius=args.nms_radius,
                min_distance=args.min_distance,
                max_seeds=args.max_seeds,
            )
            write_json_document(args.output_json, document)
            print(
                f"wrote {len(document['requests'])} seed requests to {args.output_json} "
                "(base_voxels)"
            )
            return 0

        if args.command == "vc3d-export":
            index = export_vc3d_seed_bundle_from_manifest(
                args.seed_manifest,
                args.output_dir,
                generation=args.generation,
            )
            print(index)
            return 0
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"fibergraph: error: {exc}\n")

    parser.error("unhandled command")
    return 2


def eval_main(argv=None) -> int:
    """Backward-compatible entry point for the historical ``fibergraph-eval`` command."""
    legacy = argparse.ArgumentParser(
        prog="fibergraph-eval",
        description="Evaluate FiberGraph traces against ScrollPrize-style NML skeletons",
    )
    legacy.add_argument("gt_nml")
    legacy.add_argument("pred_json")
    legacy.add_argument("--tolerance", type=float, default=3.0)
    legacy.add_argument("--spacing", type=float, default=1.0)
    args = legacy.parse_args(argv)
    return main([
        "eval", args.gt_nml, args.pred_json,
        "--tolerance", str(args.tolerance),
        "--spacing", str(args.spacing),
    ])


if __name__ == "__main__":
    raise SystemExit(main())
