from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import numpy as np

from .models import Tracklet
from .vc3d import write_vc3d_seed_bundle
from .villa_manifest import (
    FiberPredictionManifest,
    load_fiber_prediction_manifest,
    load_persisted_options_from_manifest,
)
from .villa_predictions import (
    PersistedPredictionOption,
    TraceSeedRequest,
    decode_persisted_option,
    propose_trace_seed_requests,
    seed_manifest,
)

_OPTION_RE = re.compile(r"^option_(\d+)_presence$")


def read_prediction_json(path: str | Path) -> list[Tracklet]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("traces"), list):
        raise ValueError("prediction JSON must contain a 'traces' list")
    out: list[Tracklet] = []
    for index, item in enumerate(raw["traces"]):
        if not isinstance(item, dict) or "points" not in item:
            raise ValueError(f"traces[{index}] must be an object with points")
        out.append(
            Tracklet(
                str(item.get("id", index)),
                np.asarray(item["points"], dtype=np.float64),
                float(item.get("confidence", 1.0)),
                dict(item.get("metadata", {})),
            )
        )
    return out


def load_options_from_npz(
    path: str | Path,
    *,
    manifest: FiberPredictionManifest | None = None,
) -> list[PersistedPredictionOption]:
    with np.load(path, allow_pickle=False) as data:
        indices = sorted(
            int(match.group(1))
            for key in data.files
            if (match := _OPTION_RE.match(key)) is not None
        )
        if not indices:
            raise ValueError("no option_NNN_presence keys found")
        if manifest is not None:
            unknown = sorted(set(indices) - set(manifest.option_indices))
            if unknown:
                raise ValueError(f"NPZ contains options absent from manifest: {unknown}")
        options: list[PersistedPredictionOption] = []
        for index in indices:
            prefix = f"option_{index:03d}"
            required = [f"{prefix}_presence", f"{prefix}_nx", f"{prefix}_ny"]
            missing = [key for key in required if key not in data]
            if missing:
                raise ValueError(f"missing keys for option {index}: {missing}")
            options.append(
                decode_persisted_option(
                    index,
                    data[required[0]],
                    data[required[1]],
                    data[required[2]],
                )
            )
    return options


def prepare_seed_manifest_from_npz(
    predictions_npz: str | Path,
    *,
    fiber_manifest: str | Path | None = None,
    prediction_to_base_scale: float | None = None,
    origin_zyx: tuple[float, float, float] = (0.0, 0.0, 0.0),
    threshold: float = 0.85,
    min_branch_margin: float = 0.10,
    nms_radius: int = 2,
    min_distance: float = 12.0,
    max_seeds: int | None = None,
) -> dict[str, Any]:
    manifest = None
    if fiber_manifest is not None:
        manifest = load_fiber_prediction_manifest(fiber_manifest)
        if prediction_to_base_scale is not None and not np.isclose(
            float(prediction_to_base_scale), manifest.prediction_to_base_scale
        ):
            raise ValueError(
                "prediction_to_base_scale disagrees with manifest-derived scale "
                f"{manifest.prediction_to_base_scale:g}"
            )
        scale = manifest.prediction_to_base_scale
        coordinate_space = "base_voxels"
    elif prediction_to_base_scale is not None:
        scale = float(prediction_to_base_scale)
        if not np.isfinite(scale) or scale <= 0.0:
            raise ValueError("prediction_to_base_scale must be finite and > 0")
        coordinate_space = "base_voxels"
    else:
        scale = 1.0
        coordinate_space = "prediction_voxels"

    options = load_options_from_npz(predictions_npz, manifest=manifest)
    requests = propose_trace_seed_requests(
        options,
        threshold=threshold,
        min_branch_margin=min_branch_margin,
        nms_radius=nms_radius,
        min_distance=min_distance,
        max_seeds=max_seeds,
        prediction_origin_zyx=origin_zyx,
        prediction_to_output_scale=scale,
    )
    source: dict[str, Any] = {
        "mode": "npz",
        "predictions_npz": str(predictions_npz),
        "prediction_origin_zyx": [float(v) for v in origin_zyx],
        "prediction_to_output_scale": float(scale),
    }
    if manifest is not None:
        source.update(
            {
                "manifest_version": manifest.version,
                "source_to_base": manifest.source_to_base,
                "prediction_to_base_scale": manifest.prediction_to_base_scale,
            }
        )
    return seed_manifest(
        requests,
        fiber_manifest=None if fiber_manifest is None else str(fiber_manifest),
        source=source,
        coordinate_space=coordinate_space,
    )


def prepare_seed_manifest_from_manifest(
    fiber_manifest: str | Path,
    *,
    crop_zyx: tuple[int, int, int, int, int, int] | None = None,
    threshold: float = 0.85,
    min_branch_margin: float = 0.10,
    nms_radius: int = 2,
    min_distance: float = 12.0,
    max_seeds: int | None = None,
    opener=None,
) -> dict[str, Any]:
    manifest, origin, options = load_persisted_options_from_manifest(
        fiber_manifest,
        crop_zyx=crop_zyx,
        opener=opener,
    )
    requests = propose_trace_seed_requests(
        options,
        threshold=threshold,
        min_branch_margin=min_branch_margin,
        nms_radius=nms_radius,
        min_distance=min_distance,
        max_seeds=max_seeds,
        prediction_origin_zyx=origin,
        prediction_to_output_scale=manifest.prediction_to_base_scale,
    )
    return seed_manifest(
        requests,
        fiber_manifest=str(fiber_manifest),
        coordinate_space="base_voxels",
        source={
            "mode": "direct_manifest",
            "prediction_origin_zyx": list(origin),
            "source_to_base": manifest.source_to_base,
            "prediction_to_base_scale": manifest.prediction_to_base_scale,
            "crop_zyx": None if crop_zyx is None else list(crop_zyx),
        },
    )


def write_json_document(path: str | Path, document: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return target


def parse_trace_seed_manifest(document: dict[str, Any]) -> tuple[list[TraceSeedRequest], str | None]:
    if not isinstance(document, dict):
        raise ValueError("seed manifest must be a JSON object")
    if document.get("format") != "fibergraph_trace_seed_requests" or document.get("version") != 1:
        raise ValueError("unsupported FiberGraph seed manifest")
    if document.get("coordinate_order") != "zyx":
        raise ValueError("seed manifest coordinate_order must be 'zyx'")
    requests_raw = document.get("requests")
    if not isinstance(requests_raw, list):
        raise ValueError("seed manifest requests must be a list")
    requests: list[TraceSeedRequest] = []
    for index, item in enumerate(requests_raw):
        if not isinstance(item, dict):
            raise ValueError(f"requests[{index}] must be an object")
        try:
            request = TraceSeedRequest(
                seed_zyx=tuple(float(v) for v in item["seed_zyx"]),
                option_index=int(item["option_index"]),
                axis_zyx=tuple(float(v) for v in item["axis_zyx"]),
                presence=float(item["presence"]),
                branch_margin=float(item["branch_margin"]),
                confidence=float(item["confidence"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid requests[{index}]: {exc}") from exc
        requests.append(request)
    manifest = document.get("fiber_manifest")
    if manifest is not None and not isinstance(manifest, str):
        raise ValueError("fiber_manifest must be a string or null")
    return requests, manifest


def load_trace_seed_manifest(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    # Validate the requests immediately even when the caller only needs metadata.
    parse_trace_seed_manifest(raw)
    return raw


def export_vc3d_seed_bundle_from_manifest(
    seed_manifest_path: str | Path,
    output_dir: str | Path,
    *,
    generation: int = 0,
) -> Path:
    raw = load_trace_seed_manifest(seed_manifest_path)
    if raw.get("coordinate_space") != "base_voxels":
        raise ValueError(
            "VC3D fiber JSON coordinates are base voxels; regenerate seeds with "
            "a Villa fiber manifest or an explicit prediction-to-base scale first"
        )
    requests, source_manifest = parse_trace_seed_manifest(raw)
    return write_vc3d_seed_bundle(
        output_dir,
        requests,
        source_manifest=source_manifest,
        generation=generation,
    )


__all__ = [
    "read_prediction_json",
    "load_options_from_npz",
    "prepare_seed_manifest_from_npz",
    "prepare_seed_manifest_from_manifest",
    "write_json_document",
    "parse_trace_seed_manifest",
    "load_trace_seed_manifest",
    "export_vc3d_seed_bundle_from_manifest",
]
