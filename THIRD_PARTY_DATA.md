# Third-party data notice

FiberGraph source code is MIT-licensed. The repository also contains a small benchmark fixture derived from Vesuvius Challenge data; that fixture is not covered by the MIT grant.

## Scroll 5 fiber geometry subset

File: `data/scroll5_real_subset.json`

Source annotation: `foundation/datasets/fibers-dataset/fibers_s5_06500z_02000y_04000x_500_v03.nml` in the public `ScrollPrize/villa` repository / Vesuvius Challenge fiber dataset.

Use in FiberGraph: a curated, decimated set of source annotation node coordinates used only to benchmark global fiber connectivity. Intermediate source nodes may be omitted; the benchmark may later densify the retained polyline and inject synthetic gaps/jitter.

License: Vesuvius Challenge documentation states that challenge datasets are CC BY-NC 4.0 unless otherwise noted for a specific asset. The subset in this repository therefore remains under the applicable source-data terms and is not relicensed under FiberGraph's MIT License.

Attribution: Vesuvius Challenge / ScrollPrize and the authors of the source fiber annotation.

No ownership of the underlying scan or annotation data is claimed by the FiberGraph author.
