from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Iterable

from .villa_predictions import TraceSeedRequest


def _zyx_to_xyz(point_zyx: tuple[float, float, float]) -> list[float]:
    z, y, x = (float(v) for v in point_zyx)
    return [x, y, z]


def seed_request_to_vc3d_fiber(request: TraceSeedRequest, *, generation: int = 0) -> dict:
    """Return a minimal VC3D v3 seed-only fiber document.

    Current VC3D accepts a one-control-point ``vc3d_fiber``.  In native fiber
    mode the interactive seed workflow can use the attached Fiber3D inference
    dataset to extrapolate the two open tails.  The persisted seed JSON itself
    intentionally contains no fabricated ``segment_to_next`` metadata: there is
    no span until VC3D has actually traced one.

    FiberGraph's confidence/axis metadata is kept outside this document in the
    companion seed index produced by :func:`write_vc3d_seed_bundle`, so the
    fiber JSON stays as close as possible to VC3D's native schema.
    """

    if int(generation) < 0:
        raise ValueError("generation must be >= 0")
    position_xyz = _zyx_to_xyz(request.seed_zyx)
    return {
        "type": "vc3d_fiber",
        "version": 3,
        "optimization_mode": "native_fiber_trace3d",
        "line_points": [position_xyz],
        "control_points": [{"position": position_xyz}],
        "generation": int(generation),
    }


def validate_seed_only_vc3d_fiber(document: dict) -> None:
    """Validate the subset of the VC3D v3 schema used for seed-only fibers.

    This mirrors the invariants in Villa's ``vc3d_fiber_format`` / C++
    ``FiberJson`` readers that matter before a trace exists.  It deliberately
    rejects invented segment metadata on a one-control-point seed.
    """

    if not isinstance(document, dict):
        raise ValueError("VC3D fiber must be a JSON object")
    if document.get("type") != "vc3d_fiber" or document.get("version") != 3:
        raise ValueError("expected vc3d_fiber version 3")
    if document.get("optimization_mode") != "native_fiber_trace3d":
        raise ValueError("seed fiber must use native_fiber_trace3d")
    line = document.get("line_points")
    controls = document.get("control_points")
    if not isinstance(line, list) or len(line) != 1:
        raise ValueError("seed-only fiber must contain exactly one line point")
    if not isinstance(controls, list) or len(controls) != 1:
        raise ValueError("seed-only fiber must contain exactly one control point")
    control = controls[0]
    if not isinstance(control, dict) or set(control) != {"position"}:
        raise ValueError("seed control point must contain only position")
    for label, point in (("line point", line[0]), ("control point", control["position"])):
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError(f"{label} must be [x, y, z]")
        try:
            values = [float(v) for v in point]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be numeric") from exc
        if not all(__import__("math").isfinite(v) for v in values):
            raise ValueError(f"{label} must be finite")
    if [float(v) for v in line[0]] != [float(v) for v in control["position"]]:
        raise ValueError("seed line/control positions must match")
    generation = document.get("generation", 0)
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        raise ValueError("generation must be a non-negative integer")


def write_vc3d_seed_bundle(
    directory: str | Path,
    requests: Iterable[TraceSeedRequest],
    *,
    source_manifest: str | None = None,
    generation: int = 0,
    filename_prefix: str = "fibergraph_seed",
) -> Path:
    """Write VC3D seed-only JSON files plus an auditable FiberGraph index.

    Returns the path to ``fibergraph_seed_index.json``.  The index retains the
    Fiber3D option, decoded axis and confidence values that are not native fields
    of the persisted seed-only VC3D fiber document.
    """

    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    items = []
    for index, request in enumerate(requests):
        name = f"{filename_prefix}_{index:06d}.json"
        doc = seed_request_to_vc3d_fiber(request, generation=generation)
        validate_seed_only_vc3d_fiber(doc)
        (target / name).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        items.append({
            "file": name,
            "request": {
                "seed_zyx": list(request.seed_zyx),
                "option_index": int(request.option_index),
                "axis_zyx": list(request.axis_zyx),
                "presence": float(request.presence),
                "branch_margin": float(request.branch_margin),
                "confidence": float(request.confidence),
            },
        })

    index_doc = {
        "format": "fibergraph_vc3d_seed_bundle",
        "version": 1,
        "coordinate_space": "base_voxels",
        "source_manifest": source_manifest,
        "vc3d": {
            "type": "vc3d_fiber",
            "version": 3,
            "optimization_mode": "native_fiber_trace3d",
            "coordinate_order": "xyz",
        },
        "request_coordinate_order": "zyx",
        "seed_count": len(items),
        "seeds": items,
    }
    index_path = target / "fibergraph_seed_index.json"
    index_path.write_text(json.dumps(index_doc, indent=2) + "\n", encoding="utf-8")
    return index_path


__all__ = [
    "seed_request_to_vc3d_fiber",
    "validate_seed_only_vc3d_fiber",
    "write_vc3d_seed_bundle",
]
