from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.ndimage import maximum_filter


@dataclass(frozen=True)
class SeedProposal:
    zyx: tuple[float, float, float]
    branch: int
    presence: float
    branch_margin: float
    confidence: float


def propose_seeds(
    presence_bzyx: np.ndarray,
    *,
    threshold: float = 0.85,
    min_branch_margin: float = 0.10,
    nms_radius: int = 2,
    min_distance: float = 12.0,
    max_seeds: int | None = None,
    valid_bzyx: np.ndarray | None = None,
) -> list[SeedProposal]:
    """Propose sparse, high-confidence automatic Trace2CP seed locations.

    The input is *decoded* Vesuvius fiber prediction presence with shape
    ``(branches, z, y, x)``. A seed is accepted only when one branch wins by a
    configurable margin. Spatial non-maximum suppression then keeps the strongest
    seeds far apart. This intentionally rejects branch-ambiguous regions.
    """
    p = np.asarray(presence_bzyx, dtype=np.float32)
    if p.ndim != 4 or p.shape[0] < 1:
        raise ValueError("presence_bzyx must have shape (branches,z,y,x)")
    if not np.isfinite(threshold) or not (0 <= threshold <= 1):
        raise ValueError("threshold must be finite and in [0,1]")
    if not np.isfinite(min_branch_margin) or not (0 <= min_branch_margin <= 1):
        raise ValueError("min_branch_margin must be finite and in [0,1]")
    if not np.isfinite(min_distance) or min_distance < 0 or nms_radius < 0:
        raise ValueError("distances must be finite and non-negative")
    if max_seeds is not None and max_seeds <= 0:
        raise ValueError("max_seeds must be > 0 when supplied")
    if valid_bzyx is None:
        valid = np.isfinite(p)
    else:
        valid = np.asarray(valid_bzyx, dtype=bool) & np.isfinite(p)
        if valid.shape != p.shape:
            raise ValueError("valid_bzyx must match presence shape")
    p = np.where(valid, p, -np.inf)

    # winner and runner-up at every voxel
    winner = np.argmax(p, axis=0)
    top = np.max(p, axis=0)
    if p.shape[0] == 1:
        second = np.zeros_like(top)
    else:
        second = np.partition(p, -2, axis=0)[-2]
    margin = top - second

    size = 2 * int(nms_radius) + 1
    local_max = top == maximum_filter(top, size=size, mode="constant", cval=-np.inf)
    mask = local_max & (top >= threshold) & (margin >= min_branch_margin) & np.isfinite(top)
    coords = np.argwhere(mask)
    if len(coords) == 0:
        return []

    vals = top[tuple(coords.T)]
    margins = margin[tuple(coords.T)]
    branches = winner[tuple(coords.T)]
    # Presence is primary; margin is a calibrated anti-ambiguity multiplier.
    conf = vals * np.clip(margins / max(1e-6, 1.0 - threshold), 0.0, 1.0)
    order = np.lexsort((coords[:,2], coords[:,1], coords[:,0], -margins, -vals, -conf))

    accepted: list[SeedProposal] = []
    accepted_xyz: list[np.ndarray] = []
    for j in order:
        c = coords[j].astype(np.float64)
        if accepted_xyz and min_distance > 0:
            # n is deliberately small after voxel NMS; avoid rebuilding tree each point.
            if min(float(np.linalg.norm(c - a)) for a in accepted_xyz) < min_distance:
                continue
        accepted_xyz.append(c)
        accepted.append(SeedProposal(
            zyx=tuple(float(x) for x in c),
            branch=int(branches[j]),
            presence=float(vals[j]),
            branch_margin=float(margins[j]),
            confidence=float(conf[j]),
        ))
        if max_seeds is not None and len(accepted) >= max_seeds:
            break
    return accepted
