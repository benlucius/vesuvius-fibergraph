from __future__ import annotations
from dataclasses import dataclass, asdict
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree

from .models import FiberGraphNML, Tracklet
from .nml import fiber_paths
from .geometry import resample_polyline


@dataclass(frozen=True)
class FiberMetrics:
    precision: float
    recall: float
    f1: float
    predicted_length: float
    gt_length: float
    correct_predicted_length: float
    covered_gt_length: float
    identity_switches: int
    switches_per_1000: float
    max_continuous_correct_span: float
    mean_trace_purity: float
    fragmented_gt_fibers: int
    gt_fibers_covered: int
    gt_fiber_count: int

    def to_dict(self) -> dict:
        return asdict(self)


def _gt_samples(graph: FiberGraphNML, spacing: float):
    pts, ids = [], []
    gt_lengths: dict[str, float] = defaultdict(float)
    traces: list[tuple[str, np.ndarray, np.ndarray]] = []
    for f in graph.fibers:
        for p in fiber_paths(f):
            q, s = resample_polyline(p, spacing)
            pts.append(q)
            ids.extend([f.fiber_id] * len(q))
            gt_lengths[f.fiber_id] += float(s[-1])
            traces.append((f.fiber_id, q, s))
    if not pts:
        raise ValueError("ground truth contains no sampled edges")
    return np.concatenate(pts, axis=0), np.asarray(ids, dtype=object), gt_lengths, traces


def _sample_predictions(predictions: list[Tracklet], spacing: float):
    traces = []
    total = 0.0
    for t in predictions:
        q, s = resample_polyline(t.points, spacing)
        traces.append((t, q, s))
        total += float(s[-1])
    return traces, total


def evaluate_predictions(
    gt: FiberGraphNML,
    predictions: list[Tracklet],
    tolerance: float = 3.0,
    spacing: float = 1.0,
    min_fragment_length: float = 5.0,
) -> FiberMetrics:
    """Topology-sensitive evaluation of unbranched predicted fiber traces.

    Pointwise proximity provides precision/recall, while identity switches,
    purity, fragmentation, and longest continuous correct span penalize the
    exact failure that voxel Dice misses: joining two nearby fibers into one.
    """
    if tolerance <= 0:
        raise ValueError("tolerance must be >0")
    gt_pts, gt_ids, gt_lengths, gt_traces = _gt_samples(gt, spacing)
    gt_tree = cKDTree(gt_pts)
    pred_traces, pred_total = _sample_predictions(predictions, spacing)

    if not pred_traces:
        return FiberMetrics(0.0, 0.0, 0.0, 0.0, float(sum(gt_lengths.values())), 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0, 0, len(gt.fibers))

    correct_len = 0.0
    switches = 0
    longest_span = 0.0
    purity_values: list[float] = []
    matched_by_gt: dict[str, set[str]] = defaultdict(set)

    all_pred_samples: list[np.ndarray] = []
    for t, q, s in pred_traces:
        all_pred_samples.append(q)
        dist, idx = gt_tree.query(q, k=1)
        labels = gt_ids[idx]
        valid = dist <= tolerance
        # Interval correctness: attribute each segment by both endpoints being valid and same fiber.
        if len(q) > 1:
            ds = np.diff(s)
            seg_valid = valid[:-1] & valid[1:] & (labels[:-1] == labels[1:])
            correct_len += float(ds[seg_valid].sum())
            # identity switches count only when both sides are valid; invalid gaps break continuity.
            switches += int(np.sum(valid[:-1] & valid[1:] & (labels[:-1] != labels[1:])))
            # Longest continuously correct run on one GT fiber.
            run = 0.0
            last_label = None
            for i, dsi in enumerate(ds):
                ok = bool(seg_valid[i])
                lab = labels[i] if ok else None
                if ok and lab == last_label:
                    run += float(dsi)
                elif ok:
                    run = float(dsi)
                else:
                    run = 0.0
                last_label = lab
                longest_span = max(longest_span, run)

            # matched length by GT for fragmentation statistic
            per_gt = defaultdict(float)
            for i, dsi in enumerate(ds):
                if seg_valid[i]:
                    per_gt[str(labels[i])] += float(dsi)
            for gid, L in per_gt.items():
                if L >= min_fragment_length:
                    matched_by_gt[gid].add(t.track_id)

        if np.any(valid):
            vals, cnt = np.unique(labels[valid], return_counts=True)
            purity_values.append(float(cnt.max() / cnt.sum()))
        else:
            purity_values.append(0.0)

    precision = correct_len / pred_total if pred_total else 0.0

    # GT coverage is measured on GT arc-length intervals, not by assigning a
    # fixed length to every sampled point.  An interval counts only when both
    # endpoints lie within tolerance of some prediction.  This avoids the
    # endpoint over-count in ``sample_count * spacing`` while retaining a
    # bounded sampling approximation controlled by ``spacing``.
    pred_pts = np.concatenate(all_pred_samples, axis=0)
    pred_tree = cKDTree(pred_pts)
    covered_gt_len = 0.0
    for _gid, q, s in gt_traces:
        if len(q) < 2:
            continue
        gt_dist, _ = pred_tree.query(q, k=1)
        covered = gt_dist <= tolerance
        ds = np.diff(s)
        covered_gt_len += float(ds[covered[:-1] & covered[1:]].sum())
    gt_total = float(sum(gt_lengths.values()))
    covered_gt_len = min(covered_gt_len, gt_total)
    recall = covered_gt_len / gt_total if gt_total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fragmented = sum(1 for tids in matched_by_gt.values() if len(tids) > 1)
    covered_count = sum(1 for tids in matched_by_gt.values() if tids)
    switches_per_1000 = switches * 1000.0 / pred_total if pred_total else 0.0

    return FiberMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        predicted_length=pred_total,
        gt_length=gt_total,
        correct_predicted_length=correct_len,
        covered_gt_length=covered_gt_len,
        identity_switches=switches,
        switches_per_1000=switches_per_1000,
        max_continuous_correct_span=longest_span,
        mean_trace_purity=float(np.mean(purity_values)) if purity_values else 0.0,
        fragmented_gt_fibers=fragmented,
        gt_fibers_covered=covered_count,
        gt_fiber_count=len(gt.fibers),
    )
