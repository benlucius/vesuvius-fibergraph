# Changelog

## 0.1.0 — 2026-09-13

First public software release.

- Finalized the Gate-1 precision-first linker and Villa/VC3D adapter from RC1.
- Added the MIT License and package license metadata.
- Retained the conservative scientific claim boundary: no end-to-end CT/Fiber3D accuracy claim until Gate 2 is run on real persisted predictions.

## 0.1.0rc1 — 2026-09-13

Initial release candidate.

- Precision-first endpoint linker with ambiguity refusal, mutual-best admission, and global one-endpoint matching.
- Topology-sensitive evaluation including identity switches, purity, fragmentation, and continuous correct span.
- Gate-1 held-out benchmark on real Scroll 5 human skeleton geometry with synthetic fragmentation/jitter.
- Stricter GT arc-length interval coverage metric replacing sample-count approximation.
- Villa Fiber3D persisted `presence/nx/ny` decoder and conservative seed proposal.
- Strict Lasagna v2 Fiber3D manifest parser and manifest-derived prediction-to-base coordinate scaling.
- Local direct-manifest Zarr loading plus NPZ interchange path.
- Minimal seed-only VC3D v3 export with no fabricated trace provenance.
- Unified `fibergraph` CLI and backward-compatible `fibergraph-eval` command.
- Coordinate-safety guard that refuses VC3D export from unscaled prediction-grid seeds.
