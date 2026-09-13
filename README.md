# FiberGraph

FiberGraph is a conservative global assembler and seed-proposal layer for Vesuvius papyrus fiber tracing.

The project targets a specific gap in the current Vesuvius workflow: native Fiber3D / Trace2CP machinery can continue a fiber from local evidence, but collection-scale use still needs reliable automatic seed proposal, conservative long-range assembly, deduplication, and evaluation that penalizes identity switches rather than rewarding raw coverage.

FiberGraph is designed around one rule:

> **Prefer to stop rather than connect the wrong fiber.**

This repository contains a tested `0.1.0` implementation, a held-out geometry benchmark on a small Scroll 5 fiber-skeleton subset, Villa Fiber3D manifest/prediction adapters, VC3D v3 seed export, and reproducible evidence artifacts.

## What is implemented

- global endpoint linking with one-use endpoint constraints;
- mutual-local-best acceptance to reject asymmetric ambiguous joins;
- distance, tangent and ambiguity gates;
- connected-length / fragmentation / identity-switch evaluation;
- WebKnossos `.nml` parsing for Vesuvius fiber skeletons;
- automatic high-confidence seed proposal from Fiber3D `presence/nx/ny` prediction volumes;
- support for both single-option `presence/nx/ny` and multi-option `option_NNN_presence/nx/ny` Villa manifests;
- Villa manifest coordinate/scale validation;
- VC3D version-3 seed-only fiber JSON export;
- CLI workflows and 34 regression tests.

## Current evidence

### Gate 1 — held-out real fiber geometry

Gate 1 uses real Scroll 5 manually annotated fiber geometry, with synthetic fragmentation/noise applied only to create a controlled assembly stress test. The held-out identities are never used by the linker.

With parameters frozen before evaluation:

| condition | proposed joins | correct joins | wrong joins | join precision | join recall | identity switches |
|---|---:|---:|---:|---:|---:|---:|
| clean | 10 | 10 | 0 | 100% | 100% | 0 |
| medium | 9 | 9 | 0 | 100% | 90% | 0 |
| stress | 10 | 10 | 0 | 100% | 66.7% | 0 |

Under stress, FiberGraph deliberately refuses ambiguous links instead of increasing recall by crossing to a neighboring fiber.

See [`GATE1_STATUS.md`](GATE1_STATUS.md) and [`results/gate1_heldout.json`](results/gate1_heldout.json).

### Gate 2 — not yet claimed

Gate 2 is intentionally still open. A release-quality claim requires tracklets/seeds produced from real Fiber3D inference without ground-truth assistance, followed by evaluation against withheld skeletons and then a downstream tracing/unwrapping experiment.

The adapter and export path are implemented, but this repository does **not** claim an end-to-end CT improvement yet.

See [`GATE2_ADAPTER_STATUS.md`](GATE2_ADAPTER_STATUS.md).

## Install

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The `0.1.0` source tree passes 34/34 tests.

## CLI

```bash
fibergraph --help
```

Evaluate predicted tracks against a reference skeleton set:

```bash
fibergraph eval \
  --ground-truth path/to/reference.nml \
  --prediction path/to/prediction.nml
```

Generate conservative seed requests from a Villa Fiber3D manifest:

```bash
fibergraph seeds-from-manifest \
  path/to/fiber.lasagna.json \
  --output seeds.json
```

Export those seed requests as VC3D `vc3d_fiber` v3 JSON files:

```bash
fibergraph export-vc3d-seeds \
  seeds.json \
  --output-dir vc3d_seeds
```

## Why connectivity metrics instead of Dice alone?

A fiber tracer can obtain good voxel overlap while making a catastrophic topological error: jumping from one physical papyrus fiber to its neighbor. FiberGraph therefore treats identity continuity as a first-class metric.

The benchmark reports, among other quantities:

- correctly connected arclength;
- link precision and recall;
- identity switches;
- fragmentation;
- maximum continuous correct span;
- per-trace purity.

The intended operating point is high precision first, then maximum useful connected length at that precision.

## Relationship to Vesuvius / Villa

FiberGraph does not replace the native Vesuvius Fiber3D model or VC3D Trace2CP implementation. It is meant to sit around those components:

```text
Fiber3D prediction
        ↓
conservative seed proposal
        ↓
native Villa / VC3D tracing
        ↓
tracklets
        ↓
FiberGraph global assembly + refusal
        ↓
long high-confidence fiber instances
        ↓
downstream geometry / spiral-fit experiments
```

This separation is intentional: the existing Vesuvius tracer already contains sophisticated local beam-search logic. FiberGraph focuses on automatic global use and auditable connectivity decisions rather than reimplementing it.

## Reproducibility

Important evidence files are committed under `results/` rather than represented only by prose. The project also ships scripts used to generate the synthetic and Gate 1 benchmark outputs.

```bash
python scripts/run_synthetic_benchmark.py
python scripts/run_gate1_benchmark.py
pytest -q
```

## Licensing

FiberGraph **code** is released under the [MIT License](LICENSE).

The small Scroll 5 benchmark subset under `data/` is derived from Vesuvius Challenge dataset material and is **not relicensed under MIT**. See [`THIRD_PARTY_DATA.md`](THIRD_PARTY_DATA.md) for source/licensing notice. Vesuvius Challenge datasets are generally distributed under CC BY-NC 4.0 unless a specific asset states otherwise.

## Status

`0.1.0` is a software release and a reproducible Gate 1 result. It should not be cited as evidence that FiberGraph already improves end-to-end virtual unwrapping. That is the next experimental gate.
