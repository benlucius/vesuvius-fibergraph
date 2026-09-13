"""FiberGraph: conservative global fiber-instance assembly and evaluation."""

try:
    from importlib.metadata import PackageNotFoundError, version
    __version__ = version("fibergraph")
except PackageNotFoundError:  # source-tree fallback before installation
    __version__ = "0.1.0"

from .models import FiberGraphNML, FiberInstance, Tracklet
from .metrics import evaluate_predictions, FiberMetrics
from .linker import LinkConfig, assemble_tracklets
from .seeding import SeedProposal, propose_seeds
from .villa_predictions import (
    PersistedPredictionOption, TraceSeedRequest, decode_persisted_option,
    propose_trace_seed_requests, write_seed_manifest,
)

__all__ = [
    "__version__",
    "FiberGraphNML", "FiberInstance", "Tracklet",
    "FiberMetrics", "evaluate_predictions",
    "LinkConfig", "assemble_tracklets", "SeedProposal", "propose_seeds",
    "PersistedPredictionOption", "TraceSeedRequest", "decode_persisted_option",
    "propose_trace_seed_requests", "write_seed_manifest",
]
