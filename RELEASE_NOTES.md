# FiberGraph 0.1.0 release notes

FiberGraph 0.1.0 is the first public software release of the precision-first global papyrus-fiber connectivity layer. It is released under the MIT License.

The measured claim is deliberately limited: on the held-out Gate-1 benchmark built from real human Scroll 5 skeleton geometry plus controlled artificial fragmentation/jitter, the fixed linker makes 10/10, 9/9, and 10/10 correct predicted joins in clean, medium, and stress conditions respectively, with zero wrong joins. Under stress it refuses five true joins rather than guessing.

The release also contains the Villa/VC3D integration adapter needed for the next scientific gate. It validates Fiber3D `presence/nx/ny` prediction manifests, derives persisted prediction-grid to VC3D-base coordinate scaling, proposes conservative seeds, and exports minimal native-mode VC3D v3 seed files. A coordinate-safety guard blocks VC3D export when seed coordinates have not been converted to base voxels.

No end-to-end CT/Fiber3D accuracy improvement is claimed in 0.1.0. Gate 2 remains open until a real native Fiber3D checkpoint or persisted prediction crop is run without using NML coordinates to generate candidate traces.

## License

MIT License, Copyright (c) 2026 Ben Lucius. See `LICENSE`.
