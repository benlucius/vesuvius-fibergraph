from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
import numpy as np

Array = np.ndarray


@dataclass(frozen=True)
class FiberInstance:
    """One manually annotated fiber graph from WebKnossos NML."""
    fiber_id: str
    name: str
    nodes: dict[str, Array]
    edges: tuple[tuple[str, str], ...]

    def degree(self) -> dict[str, int]:
        d = {k: 0 for k in self.nodes}
        for a, b in self.edges:
            if a in d and b in d:
                d[a] += 1
                d[b] += 1
        return d


@dataclass(frozen=True)
class FiberGraphNML:
    fibers: tuple[FiberInstance, ...]
    scale_xyz: tuple[float, float, float] = (1.0, 1.0, 1.0)
    unit: str = "voxel"


@dataclass
class Tracklet:
    """Ordered, unbranched candidate trace in XYZ coordinates."""
    track_id: str
    points: Array
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.points = np.asarray(self.points, dtype=np.float64)
        if self.points.ndim != 2 or self.points.shape[1] != 3 or len(self.points) < 2:
            raise ValueError("points must have shape (N,3), N>=2")
        if not np.isfinite(self.points).all():
            raise ValueError("points must be finite")
        self.confidence = float(self.confidence)
        if not np.isfinite(self.confidence) or not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be finite and in [0,1]")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")

    @property
    def length(self) -> float:
        return float(np.linalg.norm(np.diff(self.points, axis=0), axis=1).sum())

    def reversed(self) -> "Tracklet":
        return Tracklet(self.track_id, self.points[::-1].copy(), self.confidence, dict(self.metadata))

    def endpoint(self, side: int) -> Array:
        return self.points[0 if side == 0 else -1]

    def tangent(self, side: int, window: int = 4) -> Array:
        n = min(window, len(self.points) - 1)
        if side == 0:
            v = self.points[0] - self.points[n]
        else:
            v = self.points[-1] - self.points[-1 - n]
        norm = np.linalg.norm(v)
        if norm == 0:
            return np.zeros(3, dtype=np.float64)
        return v / norm


def total_polyline_length(polylines: Iterable[Array]) -> float:
    return float(sum(np.linalg.norm(np.diff(np.asarray(p), axis=0), axis=1).sum() for p in polylines if len(p) >= 2))
