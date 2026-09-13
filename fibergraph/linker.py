from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
import numpy as np
import networkx as nx

from .models import Tracklet
from .geometry import angle_degrees


@dataclass(frozen=True)
class LinkConfig:
    max_gap: float = 20.0
    max_angle_deg: float = 25.0
    distance_weight: float = 1.0
    angle_weight: float = 0.35
    confidence_weight: float = 2.0
    min_score: float = 0.0
    ambiguity_margin: float = 0.15
    join_samples: int = 2
    require_mutual_best: bool = True


@dataclass(frozen=True)
class CandidateLink:
    a: tuple[int, int]
    b: tuple[int, int]
    gap: float
    angle_a: float
    angle_b: float
    score: float


def _candidate(a: Tracklet, ai: int, aside: int, b: Tracklet, bi: int, bside: int, cfg: LinkConfig) -> CandidateLink | None:
    pa, pb = a.endpoint(aside), b.endpoint(bside)
    v = pb - pa
    gap = float(np.linalg.norm(v))
    if gap == 0 or gap > cfg.max_gap:
        return None
    d = v / gap
    # Endpoint tangents point outward from each tracklet. To bridge A -> B,
    # A should point toward B and B outward tangent should point back toward A.
    ta, tb = a.tangent(aside), b.tangent(bside)
    aa = angle_degrees(ta, d)
    ab = angle_degrees(tb, -d)
    if aa > cfg.max_angle_deg or ab > cfg.max_angle_deg:
        return None
    angle_pen = (aa + ab) / max(cfg.max_angle_deg, 1e-9)
    conf = min(a.confidence, b.confidence)
    score = cfg.confidence_weight * conf - cfg.distance_weight * (gap / cfg.max_gap) - cfg.angle_weight * angle_pen
    if score < cfg.min_score:
        return None
    return CandidateLink((ai, aside), (bi, bside), gap, aa, ab, score)


def candidate_links(tracklets: list[Tracklet], cfg: LinkConfig = LinkConfig()) -> list[CandidateLink]:
    out = []
    for (ai, a), (bi, b) in combinations(enumerate(tracklets), 2):
        for aside in (0, 1):
            for bside in (0, 1):
                c = _candidate(a, ai, aside, b, bi, bside, cfg)
                if c is not None:
                    out.append(c)
    return sorted(out, key=lambda c: c.score, reverse=True)


def conservative_links(tracklets: list[Tracklet], cfg: LinkConfig = LinkConfig()) -> list[CandidateLink]:
    """Global endpoint matching with an ambiguity refusal rule.

    Each endpoint can be used once. Before matching, a link is suppressed when
    either endpoint has a nearly-equal alternative. This explicitly trades
    recall for identity preservation.
    """
    cand = candidate_links(tracklets, cfg)
    by_endpoint: dict[tuple[int, int], list[CandidateLink]] = {}
    for c in cand:
        by_endpoint.setdefault(c.a, []).append(c)
        by_endpoint.setdefault(c.b, []).append(c)

    # Precision-first admission.  A candidate must be the unique local winner
    # at both endpoints (unless the caller explicitly disables this guard), and
    # each endpoint must have enough score margin over its runner-up.  Merely
    # suppressing ambiguous endpoints is not sufficient: global matching can
    # otherwise choose a locally second-best cross-fiber edge to increase total
    # graph weight.
    top_by_endpoint: dict[tuple[int, int], CandidateLink] = {}
    margin_by_endpoint: dict[tuple[int, int], float] = {}
    for ep, xs in by_endpoint.items():
        ranked = sorted(xs, key=lambda x: x.score, reverse=True)
        top_by_endpoint[ep] = ranked[0]
        margin_by_endpoint[ep] = (
            ranked[0].score - ranked[1].score if len(ranked) >= 2 else float("inf")
        )

    safe: list[CandidateLink] = []
    for c in cand:
        if any(margin_by_endpoint.get(ep, float("inf")) < cfg.ambiguity_margin for ep in (c.a, c.b)):
            continue
        if cfg.require_mutual_best and any(top_by_endpoint.get(ep) is not c for ep in (c.a, c.b)):
            continue
        safe.append(c)

    G = nx.Graph()
    for c in safe:
        G.add_edge(c.a, c.b, weight=c.score, candidate=c)
    matching = nx.algorithms.matching.max_weight_matching(G, maxcardinality=False, weight="weight")
    chosen = []
    lookup = {frozenset((c.a, c.b)): c for c in safe}
    for a, b in matching:
        c = lookup.get(frozenset((a, b)))
        if c is not None:
            chosen.append(c)
    return sorted(chosen, key=lambda c: c.score, reverse=True)


def _oriented_points(t: Tracklet, enter_side: int) -> np.ndarray:
    # If entering at side 0, path runs 0 -> 1. If entering at 1, reverse.
    return t.points if enter_side == 0 else t.points[::-1]


def assemble_tracklets(tracklets: list[Tracklet], cfg: LinkConfig = LinkConfig()) -> tuple[list[Tracklet], list[CandidateLink]]:
    """Assemble non-branching fibers from globally matched endpoint links."""
    links = conservative_links(tracklets, cfg)
    ep_link: dict[tuple[int, int], tuple[tuple[int, int], CandidateLink]] = {}
    for c in links:
        ep_link[c.a] = (c.b, c)
        ep_link[c.b] = (c.a, c)

    visited: set[int] = set()
    out: list[Tracklet] = []

    # Components are chains because every endpoint has degree <=1 and tracklets have two endpoints.
    def build(start_idx: int, enter_side: int) -> Tracklet:
        parts = []
        ids = []
        member_indices = []
        i, side = start_idx, enter_side
        while i not in visited:
            visited.add(i)
            member_indices.append(i)
            ids.append(tracklets[i].track_id)
            p = _oriented_points(tracklets[i], side)
            if parts:
                # Straight interpolation across the unmatched spatial gap. It is
                # marked in metadata; later Trace2CP/CT evidence can replace it.
                prev = parts[-1][-1]
                nxt = p[0]
                gap = np.linalg.norm(nxt - prev)
                if gap > 0 and cfg.join_samples > 0:
                    bridge = np.linspace(prev, nxt, cfg.join_samples + 2)[1:-1]
                    parts.append(bridge)
            parts.append(p)
            exit_side = 1 - side
            nxt = ep_link.get((i, exit_side))
            if nxt is None:
                break
            (j, jside), _ = nxt
            if j in visited:
                break
            i, side = j, jside
        points = np.concatenate(parts, axis=0)
        conf = min(tracklets[k].confidence for k in member_indices)
        return Tracklet(
            "+".join(ids),
            points,
            confidence=conf,
            metadata={"members": ids, "member_indices": member_indices},
        )

    # Prefer free endpoints so chains are oriented end-to-end.
    for i in range(len(tracklets)):
        if i in visited:
            continue
        free = [s for s in (0, 1) if (i, s) not in ep_link]
        if free:
            out.append(build(i, free[0]))
    # Any cycles (rare) are still emitted rather than dropped.
    for i in range(len(tracklets)):
        if i not in visited:
            out.append(build(i, 0))
    return out, links
