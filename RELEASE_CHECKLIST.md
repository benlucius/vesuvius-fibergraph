# FiberGraph release checklist

## 0.1.0 release completed

- [x] Gate-1 linker configuration frozen before held-out transcription.
- [x] Held-out Gate-1 link precision measured with zero wrong joins in clean/medium/stress cases.
- [x] Metrics use GT arc-length intervals rather than `sample_count * spacing` recall approximation.
- [x] Villa persisted `presence/nx/ny` options decoded and branch ambiguity rejected.
- [x] Prediction-grid → VC3D-base coordinate scale derived from the Villa manifest.
- [x] Unscaled prediction-coordinate seed manifests are refused by VC3D export.
- [x] Minimal seed-only VC3D v3 schema tested.
- [x] Unified CLI added; legacy evaluation entry point retained.
- [x] Source test suite passes.
- [x] Wheel and sdist build successfully; sdist tests and isolated wheel-import/CLI smoke pass.
- [x] MIT License selected by the author and included in source and package metadata.
- [x] Final `0.1.0` artifacts rebuilt and checksummed.

## Scientific gate before claiming end-to-end Fiber3D improvement

- [ ] Obtain a real native Fiber3D checkpoint or persisted prediction crop.
- [ ] Generate seeds without using NML/GT coordinates.
- [ ] Run the existing VC3D native fiber tracer on those seeds.
- [ ] Convert traced outputs to FiberGraph tracklets.
- [ ] Evaluate on a withheld annotated region with identity-switch metrics.
- [ ] Record failure cases and refusal rate, not only aggregate accuracy.

The public `0.1.0` software release is valid before scientific Gate 2 is passed because its claims remain limited to Gate 1 and the integration adapter.
