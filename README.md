# FiberGraph — conservative global papyrus-fiber assembly

> Independent open-source research tooling for the Vesuvius Challenge ecosystem. This project is not an official Vesuvius Challenge repository.

FiberGraph is a precision-first connectivity layer for Vesuvius papyrus fibers. It sits **above** the local Fiber3D / native VC3D tracer already present in `ScrollPrize/villa`: local predictions and traces become tracklets, FiberGraph decides which endpoints can be joined safely, and ambiguous joins are refused instead of guessed.

The current 0.1.0 release is intentionally narrow. It contains a validated global linker, topology-aware evaluation, a Gate-1 benchmark on real human Scroll 5 skeleton geometry, and an adapter from Villa Fiber3D persisted predictions to base-coordinate VC3D seed-only fibers. It does **not** claim end-to-end recovery from CT yet.

## Why this exists

Pointwise overlap is not enough for fiber tracing. Two nearby fibers can both look locally correct while a single wrong bridge silently swaps identity. FiberGraph therefore makes identity preservation the primary constraint:

- distance and endpoint-tangent gates;
- endpoint-local ambiguity margins;
- mutual-best admission before global matching;
- one-link-per-endpoint maximum-weight matching;
- explicit refusal when competing continuations are too close;
- topology metrics including identity switches, trace purity, fragmentation, and longest continuous correct span.

## Install

Python 3.11+ is required.

```bash
python -m pip install .
```

Direct reading of local Villa OME-Zarr prediction channels is optional:

```bash
python -m pip install '.[villa]'
```

The legacy `fibergraph-eval` command is retained; new workflows use the unified `fibergraph` CLI.

## Quick start

Evaluate predicted traces against a WebKnossos/ScrollPrize NML:

```bash
fibergraph eval ground_truth.nml predictions.json --tolerance 3 --spacing 1
```

Prepare conservative seed requests from an NPZ crop of persisted Fiber3D options. Supplying the Villa manifest is strongly preferred because FiberGraph derives the exact prediction-grid to VC3D-base scale from it:

```bash
fibergraph seeds npz predictions.npz seeds.json \
  --fiber-manifest fiber.lasagna.json \
  --origin-zyx Z Y X
```

Or read local persisted Villa prediction channels directly from the manifest:

```bash
fibergraph seeds manifest fiber.lasagna.json seeds.json \
  --crop-zyx Z0 Z1 Y0 Y1 X0 X1
```

Convert **base-coordinate** seed requests to minimal VC3D v3 seed-only fibers:

```bash
fibergraph vc3d-export seeds.json vc3d_seeds/
```

FiberGraph refuses the final export when a seed manifest is still in prediction-grid coordinates. This prevents a prediction-resolution index from being silently interpreted as a VC3D base-volume coordinate.

## Gate 1 — real human skeleton geometry

`data/scroll5_real_subset.json` is a curated, decimated coordinate subset copied from the public Scroll 5 human WebKnossos annotation:

`foundation/datasets/fibers-dataset/fibers_s5_06500z_02000y_04000x_500_v03.nml`

Every stored XYZ point is a source annotation node; intermediate source nodes may be omitted. The benchmark densifies these real polylines and then injects controlled fragmentation, gaps, and jitter. Thus Gate 1 tests global assembly on **real manually traced geometry**, but the fragments are synthetic and no CT/model inference is involved.

The linker configuration was frozen on development fibers before the five held-out fibers (`186`, `187`, `189`, `196`, `197`) were transcribed into the benchmark subset:

```text
max_gap = 32 vox
max_angle = 30 deg
ambiguity_margin = 0.15
require_mutual_best = true
```

Held-out link results:

| condition | correct / predicted | wrong | true-link recall | identity switches | longest correct span before → after |
|---|---:|---:|---:|---:|---:|
| clean | 10 / 10 | 0 | 100% | 0 | 317.5 → 965.0 vox |
| medium | 9 / 9 | 0 | 90% | 0 | 365.4 → 1102.1 vox |
| stress | 10 / 10 | 0 | 66.7% | 0 | 218.0 → 218.0 vox |

The stress case deliberately leaves 5/15 true joins unresolved rather than creating a cross-fiber join. With the stricter interval-based coverage metric, geometry recall rises from about 92.45% to 96.94% after assembly in that stress case; link precision remains 100% in all three held-out conditions.

Reproduce it with:

```bash
python scripts/run_gate1_benchmark.py
```

Machine-readable evidence is in `results/gate1_development.json` and `results/gate1_heldout.json`.

## Gate 2 — Villa Fiber3D → VC3D native tracing

Villa persists each Fiber3D option as `presence`, `nx`, and `ny` prediction channels. FiberGraph can decode those channels, reject low-confidence or branch-ambiguous points, apply spatial NMS, and emit sparse seed requests.

The coordinate contract is explicit:

```text
prediction_to_base_scale = source_to_base * 2**group.scaledown
base_seed_zyx = (prediction_index_zyx + crop_origin_zyx) * prediction_to_base_scale
```

`fibergraph.villa_manifest` checks that every detected option has a complete `presence/nx/ny` triplet and that all option channels have one consistent persisted prediction scale. Seed export then converts ZYX requests to VC3D XYZ and writes a minimal version-3 `vc3d_fiber` with `optimization_mode = native_fiber_trace3d`. It does not fabricate `segment_to_next` provenance before VC3D has actually traced a span.

A true Gate-2 score is **not yet claimed**. The remaining hard requirement is a real native Fiber3D prediction crop/checkpoint on a withheld annotated region, followed by native VC3D tracing without using NML geometry to generate the candidates. See `GATE2_ADAPTER_STATUS.md`.

## Tests and reproducibility

Run:

```bash
python -m pytest
python scripts/run_synthetic_benchmark.py
python scripts/run_gate1_benchmark.py
```

The 0.1.0 release has 34 automated tests covering NML parsing, linker behavior, topology metrics, Gate-1 invariants, seed NMS, compact Villa axis decoding, prediction-manifest scale handling, NPZ/direct-manifest seed workflows, VC3D seed-only schema, coordinate safety, and unified CLI smoke paths.

## Repository layout

```text
fibergraph/      core package
scripts/         benchmark and compatibility wrappers
tests/           unit/integration tests
data/            curated Gate-1 real-geometry subset
results/         committed machine-readable benchmark/smoke evidence
GATE1_STATUS.md  Gate-1 methodology and limitations
GATE2_ADAPTER_STATUS.md  current Villa/VC3D integration boundary
```

## Release status

This tree is `0.1.0` and is released under the MIT License. It is a final software release of the Gate-1 linker and Villa/VC3D integration adapter, **not** a claim of end-to-end CT/Fiber3D tracing accuracy. A Gate-2 scientific claim still requires real Fiber3D end-to-end evidence. See `RELEASE_CHECKLIST.md`.

## License

FiberGraph **code** is released under the MIT License. See `LICENSE`.

`data/scroll5_real_subset.json` is a derived coordinate subset of the public Vesuvius Challenge Scroll 5 fiber annotation and is **not relicensed under MIT**. It remains subject to the source dataset terms (CC BY-NC 4.0 unless the source asset states otherwise). See `THIRD_PARTY_DATA.md` for provenance and attribution.
