# FiberGraph Gate 2 adapter status

Date: 2026-09-13

Gate 2 is the first end-to-end scientific gate: candidate tracklets must come from Vesuvius model predictions and native tracing without using GT skeleton geometry to construct them. The adapter is now hardened enough for that experiment, but no Gate-2 accuracy score is claimed yet.

## Current integration boundary

FiberGraph does not reimplement the local neural tracer. The intended pipeline is:

1. Villa Fiber3D inference writes persisted option channels (`presence`, `nx`, `ny`).
2. FiberGraph decodes those channels, rejects branch ambiguity, applies spatial NMS, and proposes sparse high-confidence seeds.
3. Seeds are expressed in **VC3D base-volume coordinates** and exported as minimal version-3 `vc3d_fiber` seed files using `optimization_mode: native_fiber_trace3d`.
4. VC3D's existing native fiber tracer turns those seeds/control points into local traced geometry and writes the real per-span provenance.
5. FiberGraph consumes resulting local tracklets for deduplication/global assembly and topology-sensitive evaluation.

## Coordinate contract — corrected and release-blocking if violated

Persisted prediction-array indices are not automatically VC3D base coordinates. For each Fiber3D channel group the adapter derives:

```text
prediction_to_base_scale = source_to_base * 2**group.scaledown
```

For a cropped prediction array:

```text
base_seed_zyx = (local_prediction_zyx + prediction_crop_origin_zyx)
                * prediction_to_base_scale
```

This conversion is now centralized in the adapter. A seed manifest created without a manifest or explicit scale is labeled `prediction_voxels`, and `fibergraph vc3d-export` refuses to export it. This is deliberate: silently writing prediction-grid coordinates into a VC3D base-coordinate fiber would be a severe but visually plausible integration error.

## Manifest validation

`fibergraph.villa_manifest` parses the Fiber3D subset of a Villa/Lasagna v2 manifest and requires:

- finite positive `source_to_base`;
- complete `option_NNN_presence`, `option_NNN_nx`, `option_NNN_ny` channel triplets;
- one common scaledown across each triplet;
- one common persisted prediction scale across all detected options.

It supports either separate 3D ZYX channel groups or packed 4D CZYX groups. Local OME-Zarr loading is available through the optional `fibergraph[villa]` dependency. NPZ remains a small interchange format for debugging and reproducible crops.

## VC3D seed-only handoff

A seed request is exported as a minimal native-mode v3 fiber:

```json
{
  "type": "vc3d_fiber",
  "version": 3,
  "optimization_mode": "native_fiber_trace3d",
  "line_points": [[X, Y, Z]],
  "control_points": [{"position": [X, Y, Z]}],
  "generation": 0
}
```

There is no fabricated `segment_to_next` metadata because a single seed has no traced span yet. FiberGraph-only data such as decoded local axis, option index, presence, branch margin, and confidence remains in `fibergraph_seed_index.json` beside the VC3D files.

## Precision behavior

The persisted compact `nx/ny` representation determines a local **axis**, not a signed travel direction. FiberGraph uses it only to provide auditable local orientation information and to select seed locations; it does not pretend that sign selects the final rollout direction. The native tracer is responsible for the actual traced span.

Seed selection is intentionally conservative: thresholding, per-voxel winning-option margin, spatial local maxima, and minimum-distance suppression all happen before handoff.

## What has been tested

The release-candidate suite covers:

- compact-axis decoding and normalization;
- branch-ambiguous seed rejection;
- manifest-derived base-coordinate scaling;
- rejection of incomplete or cross-scale option manifests;
- local 3D and packed CZYX prediction loading;
- refusal to export unscaled prediction coordinates to VC3D;
- seed-only v3 schema validation and XYZ conversion;
- end-to-end CLI smoke from NPZ + manifest → base-coordinate seed manifest → VC3D seed bundle.

Full project suite: **34/34 passing** at RC hardening time.

## Remaining hard gate

The Villa repository exposes the native inference path and tests reference Fiber3D snapshot identities, but the snapshot name found in the manager tests is not itself a verified public downloadable checkpoint. FiberGraph therefore does not substitute unrelated public semantic-fiber models and does not report a fake end-to-end score.

Gate 2 passes only after we obtain a real native Fiber3D prediction/checkpoint, generate seeds without NML coordinates, run native VC3D tracing, and score the resulting geometry on a withheld annotation region.
