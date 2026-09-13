from __future__ import annotations
import numpy as np
from .models import FiberGraphNML, FiberInstance, Tracklet


def _fiber(fid: str, points: np.ndarray) -> FiberInstance:
    nodes = {str(i): np.asarray(p, float) for i, p in enumerate(points)}
    edges = tuple((str(i), str(i+1)) for i in range(len(points)-1))
    return FiberInstance(fid, f"fiber_{fid}", nodes, edges)


def parallel_bundle(length: float = 100.0, separation: float = 8.0, n: int = 101) -> FiberGraphNML:
    x = np.linspace(0, length, n)
    a = np.column_stack([x, 0.35*np.sin(x/12), np.zeros(n)])
    b = np.column_stack([x, separation + 0.35*np.sin(x/12 + .2), np.zeros(n)])
    return FiberGraphNML((_fiber("A", a), _fiber("B", b)))


def split_into_tracklets(points: np.ndarray, cuts: list[tuple[int,int]], prefix: str, noise: float = 0.0, seed: int = 0) -> list[Tracklet]:
    rng = np.random.default_rng(seed)
    out = []
    for k, (a,b) in enumerate(cuts):
        p = np.asarray(points[a:b], float).copy()
        if noise:
            p += rng.normal(scale=noise, size=p.shape)
        out.append(Tracklet(f"{prefix}{k}", p, confidence=0.98))
    return out


def crossing_tracklets() -> list[Tracklet]:
    # Four fragments form two true fibers that cross spatially but have orthogonal tangents.
    return [
        Tracklet("h0", np.array([[-10.,0,0],[-6.,0,0],[-2.,0,0]]), .99),
        Tracklet("h1", np.array([[2.,0,0],[6.,0,0],[10.,0,0]]), .99),
        Tracklet("v0", np.array([[0.,-10,0],[0.,-6,0],[0.,-2,0]]), .99),
        Tracklet("v1", np.array([[0.,2,0],[0.,6,0],[0.,10,0]]), .99),
    ]
