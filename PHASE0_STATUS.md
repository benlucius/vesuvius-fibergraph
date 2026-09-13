# FiberGraph Phase 0 status

Date: 2026-09-13

## Completed

- Confirmed that `ScrollPrize/villa` already has native 3D fiber tracing / Trace2CP, so FiberGraph does **not** reimplement its local beam-search tracer.
- Defined the novelty target as autonomous global seed proposal + conservative instance assembly + deduplication/confidence + topology-sensitive evaluation.
- Implemented ScrollPrize-style WebKnossos NML parsing and round-trip writing.
- Implemented topology-sensitive metrics: length precision/recall, identity switches, switches/1000 voxels, longest continuous correct span, per-trace purity, and GT fragmentation.
- Implemented a first global endpoint linker using gap/tangent gates, maximum-weight endpoint matching, and an explicit ambiguity-refusal margin.
- Implemented automatic sparse seed proposal from decoded multi-branch presence volumes, rejecting branch-ambiguous voxels.
- Added deterministic synthetic tests and a benchmark.

## Current evidence

`pytest`: 9/9 passing.

Synthetic benchmark: two nearby curved fibers, each split into three noisy tracklets.

- Before assembly: precision 1.0000, recall 0.9769, identity switches 0, longest continuous correct span 38.68 voxels, 2 fragmented GT fibers.
- After assembly: precision 1.0000, recall 1.0000, identity switches 0, longest continuous correct span 121.23 voxels, 0 fragmented GT fibers.

This is only a unit/synthetic validation of the global logic. It is **not** evidence of Vesuvius real-data performance yet.

## Next gate

Run the same evaluator against the public manual WebKnossos fiber skeletons and generate real candidate tracklets from Vesuvius fiber-prediction/Trace2CP outputs. Do not tune on the held-out evaluation fibers. The first real-data gate is high precision with fewer identity switches and longer connected spans than a simple skeleton/connected-component baseline.
