from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np

from .geometry import resample_polyline
from .linker import CandidateLink, LinkConfig, assemble_tracklets, conservative_links
from .metrics import evaluate_predictions
from .models import FiberGraphNML, FiberInstance, Tracklet


@dataclass(frozen=True)
class FragmentConfig:
    pieces: int = 3
    spacing: float = 4.0
    gap_voxels: float = 8.0
    jitter_sigma: float = 0.0
    seed: int = 0


@dataclass(frozen=True)
class LinkMetrics:
    predicted_links: int
    correct_links: int
    wrong_links: int
    precision: float
    true_links: int
    recall: float
    refused_true_links: int

    def to_dict(self) -> dict:
        return asdict(self)


def load_curated_real_subset(path: str | Path) -> tuple[FiberGraphNML, dict]:
    raw = json.loads(Path(path).read_text())
    fibers = []
    for fid, pts in raw["fibers"].items():
        a = np.asarray(pts, dtype=np.float64)
        nodes = {str(i): p for i, p in enumerate(a)}
        edges = tuple((str(i), str(i + 1)) for i in range(len(a) - 1))
        fibers.append(FiberInstance(str(fid), f"source_fiber_{fid}", nodes, edges))
    return FiberGraphNML(tuple(fibers), tuple(raw["scale_xyz"]), raw["unit"]), raw


def stable_split(fiber_id: str) -> str:
    # Stable, no Python hash randomization. Approx 55/22/22 on larger sets.
    h = hashlib.sha256(str(fiber_id).encode()).digest()[0] % 9
    if h < 5:
        return "train"
    if h < 7:
        return "validation"
    return "heldout"


def subset_graph(graph: FiberGraphNML, ids: Iterable[str]) -> FiberGraphNML:
    wanted = set(map(str, ids))
    return FiberGraphNML(tuple(f for f in graph.fibers if f.fiber_id in wanted), graph.scale_xyz, graph.unit)


def _ordered_points(fiber: FiberInstance) -> np.ndarray:
    adj = {k: [] for k in fiber.nodes}
    for a, b in fiber.edges:
        adj[a].append(b); adj[b].append(a)
    if any(len(v) > 2 for v in adj.values()):
        raise ValueError(f"fiber {fiber.fiber_id} is branched")
    ends = sorted([k for k, v in adj.items() if len(v) == 1])
    if len(ends) != 2:
        raise ValueError(f"fiber {fiber.fiber_id} is not an open path")
    out, prev, cur = [], None, ends[0]
    while True:
        out.append(fiber.nodes[cur])
        nxt = [x for x in adj[cur] if x != prev]
        if not nxt:
            break
        prev, cur = cur, nxt[0]
    return np.stack(out)


def fragment_graph(graph: FiberGraphNML, cfg: FragmentConfig) -> tuple[list[Tracklet], set[tuple[tuple[str, int], tuple[str, int]]]]:
    rng = np.random.default_rng(cfg.seed)
    tracks: list[Tracklet] = []
    truth: set[tuple[tuple[str, int], tuple[str, int]]] = set()
    for f in graph.fibers:
        p = _ordered_points(f)
        q, s = resample_polyline(p, cfg.spacing)
        total = float(s[-1])
        cuts = np.linspace(0.0, total, cfg.pieces + 1)
        local: list[Tracklet] = []
        for i in range(cfg.pieces):
            lo, hi = cuts[i], cuts[i + 1]
            # Remove half a requested gap from each side of an internal cut.
            a = lo + (cfg.gap_voxels * 0.5 if i > 0 else 0.0)
            b = hi - (cfg.gap_voxels * 0.5 if i < cfg.pieces - 1 else 0.0)
            mask = (s >= a) & (s <= b)
            pts = q[mask].copy()
            if len(pts) < 2:
                raise ValueError("fragment settings leave fewer than two samples")
            if cfg.jitter_sigma > 0:
                pts += rng.normal(0.0, cfg.jitter_sigma, size=pts.shape)
            tid = f"{f.fiber_id}:{i}"
            local.append(Tracklet(tid, pts, metadata={"parent": f.fiber_id, "order": i}))
        offset = len(tracks)
        tracks.extend(local)
        for i in range(cfg.pieces - 1):
            # Correct physical endpoints: piece i right side -> piece i+1 left side.
            truth.add(((f.fiber_id, i), (f.fiber_id, i + 1)))
    return tracks, truth


def score_links(tracklets: list[Tracklet], links: list[CandidateLink], true_links: set) -> LinkMetrics:
    correct = 0
    for c in links:
        ai, aside = c.a; bi, bside = c.b
        a, b = tracklets[ai], tracklets[bi]
        pa, pb = str(a.metadata["parent"]), str(b.metadata["parent"])
        oa, ob = int(a.metadata["order"]), int(b.metadata["order"])
        ok = False
        if pa == pb and abs(oa - ob) == 1:
            if oa < ob:
                ok = aside == 1 and bside == 0
            else:
                ok = aside == 0 and bside == 1
        correct += int(ok)
    pred = len(links)
    true_n = len(true_links)
    return LinkMetrics(
        predicted_links=pred,
        correct_links=correct,
        wrong_links=pred - correct,
        precision=correct / pred if pred else 1.0,
        true_links=true_n,
        recall=correct / true_n if true_n else 1.0,
        refused_true_links=true_n - correct,
    )


def run_case(graph: FiberGraphNML, frag: FragmentConfig, link_cfg: LinkConfig) -> dict:
    tracks, truth = fragment_graph(graph, frag)
    before = evaluate_predictions(graph, tracks, tolerance=5.0, spacing=2.0).to_dict()
    links = conservative_links(tracks, link_cfg)
    lm = score_links(tracks, links, truth).to_dict()
    assembled, _ = assemble_tracklets(tracks, link_cfg)
    after = evaluate_predictions(graph, assembled, tolerance=5.0, spacing=2.0).to_dict()
    return {
        "fragment_config": asdict(frag),
        "link_config": asdict(link_cfg),
        "fiber_count": len(graph.fibers),
        "tracklet_count": len(tracks),
        "link_metrics": lm,
        "geometry_before": before,
        "geometry_after": after,
        "assembled_trace_count": len(assembled),
    }
