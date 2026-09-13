from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, Mapping, Any

import numpy as np

from .seeding import SeedProposal, propose_seeds


@dataclass(frozen=True)
class PersistedPredictionOption:
    """One persisted Villa Fiber3D option decoded in persisted prediction-grid voxel space.

    Villa's FiberTrace3DPredictAdapter persists each option as three uint8
    volumes: ``presence``, ``nx`` and ``ny``. The compact normal/fiber-axis
    encoding fixes z >= 0, which is sufficient here because a fiber direction is
    an *axis*: +v and -v represent the same local continuation direction.
    """

    option_index: int
    presence_zyx: np.ndarray
    axis_zyx: np.ndarray
    valid_zyx: np.ndarray

    def __post_init__(self) -> None:
        if int(self.option_index) < 0:
            raise ValueError("option_index must be >= 0")
        object.__setattr__(self, "option_index", int(self.option_index))
        p = np.asarray(self.presence_zyx, dtype=np.float32)
        a = np.asarray(self.axis_zyx, dtype=np.float32)
        v = np.asarray(self.valid_zyx, dtype=bool)
        if p.ndim != 3:
            raise ValueError("presence_zyx must have shape (z,y,x)")
        if a.shape != p.shape + (3,):
            raise ValueError("axis_zyx must have shape (z,y,x,3)")
        if v.shape != p.shape:
            raise ValueError("valid_zyx must match presence_zyx")
        object.__setattr__(self, "presence_zyx", p)
        object.__setattr__(self, "axis_zyx", a)
        object.__setattr__(self, "valid_zyx", v)


@dataclass(frozen=True)
class TraceSeedRequest:
    """A GT-free seed request for the existing Villa native fiber tracer."""

    seed_zyx: tuple[float, float, float]
    option_index: int
    axis_zyx: tuple[float, float, float]
    presence: float
    branch_margin: float
    confidence: float

    def __post_init__(self) -> None:
        seed = np.asarray(self.seed_zyx, dtype=np.float64)
        axis = np.asarray(self.axis_zyx, dtype=np.float64)
        if seed.shape != (3,) or not np.isfinite(seed).all():
            raise ValueError("seed_zyx must be a finite 3-vector")
        if axis.shape != (3,) or not np.isfinite(axis).all():
            raise ValueError("axis_zyx must be a finite 3-vector")
        norm = float(np.linalg.norm(axis))
        if norm <= 1e-6:
            raise ValueError("axis_zyx must have non-zero norm")
        axis /= norm
        option = int(self.option_index)
        if option < 0:
            raise ValueError("option_index must be >= 0")
        values = {
            "presence": float(self.presence),
            "branch_margin": float(self.branch_margin),
            "confidence": float(self.confidence),
        }
        if not all(np.isfinite(v) for v in values.values()):
            raise ValueError("seed confidence fields must be finite")
        if not (0.0 <= values["presence"] <= 1.0):
            raise ValueError("presence must be in [0,1]")
        if not (0.0 <= values["branch_margin"] <= 1.0):
            raise ValueError("branch_margin must be in [0,1]")
        if not (0.0 <= values["confidence"] <= 1.0):
            raise ValueError("confidence must be in [0,1]")
        object.__setattr__(self, "seed_zyx", tuple(float(v) for v in seed))
        object.__setattr__(self, "axis_zyx", tuple(float(v) for v in axis))
        object.__setattr__(self, "option_index", option)
        for key, value in values.items():
            object.__setattr__(self, key, value)


def decode_compact_axis_u8(nx_u8: np.ndarray, ny_u8: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Decode Villa/Lasagna compact ``nx``/``ny`` uint8 axis storage.

    The writer stores ``round(component * 127 + 128)`` after flipping the
    3-vector so z is non-negative. Quantization can push x^2+y^2 slightly above
    one; those samples are projected back to the unit disk before reconstructing
    z. Returns ``(axis_zyx, valid_zyx)``.
    """

    nx_raw = np.asarray(nx_u8)
    ny_raw = np.asarray(ny_u8)
    if nx_raw.shape != ny_raw.shape or nx_raw.ndim != 3:
        raise ValueError("nx_u8 and ny_u8 must have the same (z,y,x) shape")

    nx = (nx_raw.astype(np.float32) - 128.0) / 127.0
    ny = (ny_raw.astype(np.float32) - 128.0) / 127.0
    valid = np.isfinite(nx) & np.isfinite(ny)

    r2 = nx * nx + ny * ny
    too_large = r2 > 1.0
    # Quantized values can land just outside the unit disk. Projection is the
    # maximum-likelihood correction under isotropic component quantization.
    scale = np.ones_like(r2, dtype=np.float32)
    scale[too_large] = 1.0 / np.sqrt(np.maximum(r2[too_large], 1e-12))
    nx = nx * scale
    ny = ny * scale
    nz = np.sqrt(np.maximum(0.0, 1.0 - nx * nx - ny * ny))

    axis_xyz = np.stack([nx, ny, nz], axis=-1)
    norm = np.linalg.norm(axis_xyz, axis=-1, keepdims=True)
    good = valid & np.isfinite(norm[..., 0]) & (norm[..., 0] > 1e-6)
    axis_xyz = np.divide(
        axis_xyz,
        np.maximum(norm, 1e-12),
        out=np.zeros_like(axis_xyz),
        where=norm > 1e-12,
    )
    axis_zyx = axis_xyz[..., [2, 1, 0]].astype(np.float32)
    return axis_zyx, good


def decode_persisted_option(
    option_index: int,
    presence: np.ndarray,
    nx: np.ndarray,
    ny: np.ndarray,
) -> PersistedPredictionOption:
    """Decode one Fiber3D persisted option from uint8 or normalized presence."""

    p_raw = np.asarray(presence)
    if p_raw.ndim != 3:
        raise ValueError("presence must have shape (z,y,x)")
    if p_raw.dtype == np.uint8:
        p = p_raw.astype(np.float32) / 255.0
    else:
        p = p_raw.astype(np.float32)
        # Also accept integer-like arrays from generic readers.
        if np.issubdtype(p_raw.dtype, np.integer) and p_raw.size and float(np.nanmax(p_raw)) > 1.0:
            p = p / 255.0
    axis, axis_valid = decode_compact_axis_u8(nx, ny)
    if axis.shape[:3] != p.shape:
        raise ValueError("presence, nx and ny must have identical spatial shape")
    valid = axis_valid & np.isfinite(p) & (p >= 0.0) & (p <= 1.0)
    return PersistedPredictionOption(
        option_index=int(option_index),
        presence_zyx=np.clip(p, 0.0, 1.0),
        axis_zyx=axis,
        valid_zyx=valid,
    )


def propose_trace_seed_requests(
    options: Iterable[PersistedPredictionOption],
    *,
    threshold: float = 0.85,
    min_branch_margin: float = 0.10,
    nms_radius: int = 2,
    min_distance: float = 12.0,
    max_seeds: int | None = None,
    prediction_origin_zyx: tuple[float, float, float] = (0.0, 0.0, 0.0),
    prediction_to_output_scale: float = 1.0,
) -> list[TraceSeedRequest]:
    """Convert persisted Fiber3D options into conservative native-tracer seeds.

    ``prediction_origin_zyx`` is the crop origin in persisted prediction-array
    voxels. ``prediction_to_output_scale`` converts those array coordinates to
    the desired output coordinate system. For VC3D, use the manifest-derived
    ``source_to_base * 2**group.scaledown`` so emitted seeds are in base voxels.
    """

    opts = tuple(sorted(options, key=lambda item: item.option_index))
    if not opts:
        return []
    shape = opts[0].presence_zyx.shape
    if any(opt.presence_zyx.shape != shape for opt in opts):
        raise ValueError("all options must share a spatial shape")

    presence = np.stack([opt.presence_zyx for opt in opts], axis=0)
    valid = np.stack([opt.valid_zyx for opt in opts], axis=0)
    proposals = propose_seeds(
        presence,
        threshold=threshold,
        min_branch_margin=min_branch_margin,
        nms_radius=nms_radius,
        min_distance=min_distance,
        max_seeds=max_seeds,
        valid_bzyx=valid,
    )
    origin = np.asarray(prediction_origin_zyx, dtype=np.float64)
    if origin.shape != (3,) or not np.isfinite(origin).all():
        raise ValueError("prediction_origin_zyx must be a finite 3-vector")
    scale = float(prediction_to_output_scale)
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("prediction_to_output_scale must be finite and > 0")

    requests: list[TraceSeedRequest] = []
    for proposal in proposals:
        iz, iy, ix = (int(round(value)) for value in proposal.zyx)
        opt = opts[proposal.branch]
        axis = opt.axis_zyx[iz, iy, ix].astype(np.float64)
        norm = float(np.linalg.norm(axis))
        if not np.isfinite(norm) or norm <= 1e-6:
            continue
        axis /= norm
        global_seed = (np.asarray(proposal.zyx, dtype=np.float64) + origin) * scale
        requests.append(
            TraceSeedRequest(
                seed_zyx=tuple(float(v) for v in global_seed),
                option_index=int(opt.option_index),
                axis_zyx=tuple(float(v) for v in axis),
                presence=float(proposal.presence),
                branch_margin=float(proposal.branch_margin),
                confidence=float(proposal.confidence),
            )
        )
    return requests


def seed_manifest(
    requests: Iterable[TraceSeedRequest],
    *,
    fiber_manifest: str | None = None,
    source: Mapping[str, Any] | None = None,
    coordinate_space: str = "voxel_coordinates",
) -> dict[str, Any]:
    """Build a small auditable handoff manifest for a Villa tracing runner."""

    reqs = tuple(requests)
    return {
        "format": "fibergraph_trace_seed_requests",
        "version": 1,
        "coordinate_order": "zyx",
        "coordinate_space": str(coordinate_space),
        "fiber_manifest": fiber_manifest,
        "source": dict(source or {}),
        "requests": [
            {
                "seed_zyx": list(item.seed_zyx),
                "option_index": item.option_index,
                "axis_zyx": list(item.axis_zyx),
                "presence": item.presence,
                "branch_margin": item.branch_margin,
                "confidence": item.confidence,
            }
            for item in reqs
        ],
    }


def write_seed_manifest(
    path: str | Path,
    requests: Iterable[TraceSeedRequest],
    *,
    fiber_manifest: str | None = None,
    source: Mapping[str, Any] | None = None,
    coordinate_space: str = "voxel_coordinates",
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(seed_manifest(requests, fiber_manifest=fiber_manifest, source=source, coordinate_space=coordinate_space), indent=2),
        encoding="utf-8",
    )


__all__ = [
    "PersistedPredictionOption",
    "TraceSeedRequest",
    "decode_compact_axis_u8",
    "decode_persisted_option",
    "propose_trace_seed_requests",
    "seed_manifest",
    "write_seed_manifest",
]
