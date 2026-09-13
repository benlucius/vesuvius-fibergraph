from __future__ import annotations
import numpy as np


def cumulative_lengths(points: np.ndarray) -> np.ndarray:
    p = np.asarray(points, dtype=np.float64)
    if len(p) == 0:
        return np.empty(0)
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])


def resample_polyline(points: np.ndarray, spacing: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Uniform arc-length samples plus sample arc coordinates."""
    p = np.asarray(points, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 3 or len(p) < 2:
        raise ValueError("polyline must have shape (N,3), N>=2")
    if spacing <= 0:
        raise ValueError("spacing must be >0")
    s = cumulative_lengths(p)
    L = float(s[-1])
    if L == 0:
        return p[:1].copy(), np.array([0.0])
    q = np.arange(0.0, L, spacing)
    if not np.isclose(q[-1] if len(q) else -1, L):
        q = np.append(q, L)
    out = np.column_stack([np.interp(q, s, p[:, d]) for d in range(3)])
    return out, q


def endpoint_tangent(points: np.ndarray, side: int, window: int = 4) -> np.ndarray:
    p = np.asarray(points, dtype=np.float64)
    n = min(window, len(p) - 1)
    if side == 0:
        v = p[0] - p[n]
    else:
        v = p[-1] - p[-1 - n]
    norm = np.linalg.norm(v)
    return v / norm if norm else np.zeros(3)


def angle_degrees(a: np.ndarray, b: np.ndarray, unoriented: bool = False) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 180.0
    c = float(np.dot(a, b) / (na * nb))
    if unoriented:
        c = abs(c)
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))
