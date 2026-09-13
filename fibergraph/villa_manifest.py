from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Mapping, Any


_CHANNEL_RE = re.compile(r"^option_(\d+)_(presence|nx|ny)$")
_REQUIRED_KINDS = ("presence", "nx", "ny")


@dataclass(frozen=True)
class FiberPredictionChannel:
    option_index: int
    kind: str
    group_name: str
    zarr_path: str
    scaledown_power: int
    channel_index: int


@dataclass(frozen=True)
class FiberPredictionManifest:
    path: Path
    version: int
    source_to_base: float
    base_shape_zyx: tuple[int, int, int] | None
    channels: Mapping[tuple[int, str], FiberPredictionChannel]
    option_indices: tuple[int, ...]
    prediction_to_base_scale: float

    def channel(self, option_index: int, kind: str) -> FiberPredictionChannel:
        try:
            return self.channels[(int(option_index), str(kind))]
        except KeyError as exc:
            raise KeyError(f"missing Fiber3D channel option_{int(option_index):03d}_{kind}") from exc

    def resolved_local_zarr_path(self, option_index: int, kind: str) -> Path:
        raw = self.channel(option_index, kind).zarr_path
        if "://" in raw:
            raise ValueError("remote zarr paths cannot be resolved as local paths")
        path = Path(raw)
        return path if path.is_absolute() else (self.path.parent / path).resolve()


def _finite_positive(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{label} must be finite and > 0")
    return result


def load_fiber_prediction_manifest(path: str | Path) -> FiberPredictionManifest:
    """Parse the Fiber3D subset of a Villa/Lasagna v2 prediction manifest.

    Villa persists one or more options named ``option_NNN_presence/nx/ny``.
    Native VC3D uses manifest base coordinates.  The physical coordinate scale
    of every persisted prediction sample is
    ``source_to_base * 2**group.scaledown``; all three channels and all options
    must agree for FiberGraph's branch-wise NMS.
    """

    manifest_path = Path(path).resolve()
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fiber manifest must contain a JSON object")
    version = int(raw.get("version", 1))
    if version != 2:
        raise ValueError(f"expected Lasagna manifest version 2, got {version}")
    source_to_base = _finite_positive(raw.get("source_to_base"), "source_to_base")

    bshape_raw = raw.get("base_shape_zyx")
    base_shape = None
    if bshape_raw is not None:
        if not isinstance(bshape_raw, list) or len(bshape_raw) != 3:
            raise ValueError("base_shape_zyx must contain three integers")
        base_shape = tuple(int(v) for v in bshape_raw)
        if any(v <= 0 for v in base_shape):
            raise ValueError("base_shape_zyx values must be positive")

    groups = raw.get("groups")
    if not isinstance(groups, dict) or not groups:
        raise ValueError("fiber manifest has no groups")

    found: dict[tuple[int, str], FiberPredictionChannel] = {}
    scales: dict[tuple[int, str], float] = {}
    for group_name, group_raw in groups.items():
        if not isinstance(group_raw, dict):
            continue
        zarr_path = str(group_raw.get("zarr", "")).strip()
        if not zarr_path:
            continue
        scaledown = group_raw.get("scaledown")
        if isinstance(scaledown, bool) or not isinstance(scaledown, int) or scaledown < 0:
            raise ValueError(f"group {group_name!r} scaledown must be a non-negative integer")
        channels = group_raw.get("channels")
        if not isinstance(channels, list):
            raise ValueError(f"group {group_name!r} channels must be a list")
        for channel_index, channel_name_raw in enumerate(channels):
            channel_name = str(channel_name_raw)
            match = _CHANNEL_RE.match(channel_name)
            if match is not None:
                option_index = int(match.group(1))
                kind = match.group(2)
            elif channel_name in _REQUIRED_KINDS:
                # Villa intentionally drops the option_000_ prefix when a
                # Fiber3D model persists exactly one option. VC3D accepts both
                # the unprefixed triplet and prefixed multi-option channels.
                option_index = 0
                kind = channel_name
            else:
                continue
            key = (option_index, kind)
            if key in found:
                raise ValueError(f"duplicate Fiber3D channel {channel_name}")
            found[key] = FiberPredictionChannel(
                option_index=option_index,
                kind=kind,
                group_name=str(group_name),
                zarr_path=zarr_path,
                scaledown_power=int(scaledown),
                channel_index=int(channel_index),
            )
            scales[key] = source_to_base * float(1 << int(scaledown))

    if not found:
        raise ValueError("manifest contains no option_NNN_presence/nx/ny Fiber3D channels")
    option_indices = tuple(sorted({index for index, _ in found}))
    for option_index in option_indices:
        missing = [kind for kind in _REQUIRED_KINDS if (option_index, kind) not in found]
        if missing:
            raise ValueError(f"Fiber3D option {option_index} is incomplete; missing {missing}")
        option_scales = {scales[(option_index, kind)] for kind in _REQUIRED_KINDS}
        if len(option_scales) != 1:
            raise ValueError(f"Fiber3D option {option_index} channels have inconsistent scales")

    all_scales = {scales[(option_index, kind)] for option_index in option_indices for kind in _REQUIRED_KINDS}
    if len(all_scales) != 1:
        raise ValueError("Fiber3D options have inconsistent persisted prediction scales")
    prediction_to_base = next(iter(all_scales))
    return FiberPredictionManifest(
        path=manifest_path,
        version=version,
        source_to_base=source_to_base,
        base_shape_zyx=base_shape,
        channels=found,
        option_indices=option_indices,
        prediction_to_base_scale=float(prediction_to_base),
    )


__all__ = [
    "FiberPredictionChannel",
    "FiberPredictionManifest",
    "load_fiber_prediction_manifest",
]


def load_persisted_options_from_manifest(
    path: str | Path,
    *,
    crop_zyx: tuple[int, int, int, int, int, int] | None = None,
    opener=None,
):
    """Load persisted Fiber3D options from local manifest channel arrays.

    ``crop_zyx`` is ``(z0, z1, y0, y1, x0, x1)`` in prediction-array voxels.
    The default opener imports ``zarr`` lazily and opens each manifest group in
    read-only mode. Tests and downstream integrations may inject an opener that
    returns NumPy-like 3D or CZYX arrays.

    Returns ``(manifest, prediction_origin_zyx, options)``. Coordinate scaling
    to VC3D base voxels is intentionally left to
    :func:`fibergraph.villa_predictions.propose_trace_seed_requests` using
    ``manifest.prediction_to_base_scale``.
    """
    import numpy as np
    from .villa_predictions import decode_persisted_option

    manifest = load_fiber_prediction_manifest(path)
    if crop_zyx is None:
        slices = (slice(None), slice(None), slice(None))
        origin = (0.0, 0.0, 0.0)
    else:
        if len(crop_zyx) != 6:
            raise ValueError("crop_zyx must be (z0,z1,y0,y1,x0,x1)")
        z0, z1, y0, y1, x0, x1 = (int(v) for v in crop_zyx)
        if min(z0, y0, x0) < 0 or z1 <= z0 or y1 <= y0 or x1 <= x0:
            raise ValueError("crop_zyx bounds are invalid")
        slices = (slice(z0, z1), slice(y0, y1), slice(x0, x1))
        origin = (float(z0), float(y0), float(x0))

    if opener is None:
        try:
            import zarr
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "direct manifest loading requires the optional 'villa' dependency: "
                "pip install 'fibergraph[villa]'"
            ) from exc

        def opener(value):
            return zarr.open(str(value), mode="r")

    cache: dict[str, object] = {}

    def read_channel(option_index: int, kind: str) -> np.ndarray:
        channel = manifest.channel(option_index, kind)
        if "://" in channel.zarr_path:
            source = channel.zarr_path
        else:
            source = manifest.resolved_local_zarr_path(option_index, kind)
        cache_key = str(source)
        array = cache.get(cache_key)
        if array is None:
            array = opener(source)
            cache[cache_key] = array
        ndim = int(getattr(array, "ndim", np.ndim(array)))
        if ndim == 3:
            if channel.channel_index != 0:
                raise ValueError(
                    f"3D group {channel.group_name!r} cannot expose channel index {channel.channel_index}"
                )
            value = array[slices]
        elif ndim == 4:
            value = array[(channel.channel_index, *slices)]
        else:
            raise ValueError(
                f"group {channel.group_name!r} must be ZYX or CZYX, got ndim={ndim}"
            )
        return np.asarray(value)

    options = []
    for option_index in manifest.option_indices:
        options.append(
            decode_persisted_option(
                option_index,
                read_channel(option_index, "presence"),
                read_channel(option_index, "nx"),
                read_channel(option_index, "ny"),
            )
        )
    if options:
        shape = options[0].presence_zyx.shape
        if any(option.presence_zyx.shape != shape for option in options):
            raise ValueError("Fiber3D option arrays do not share one crop shape")
    return manifest, origin, options


__all__.append("load_persisted_options_from_manifest")
