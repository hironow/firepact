"""firepact: Firestore-aware Pydantic -> TypeScript contract extractor.

The Python layer's only job is to delegate schema generation to Pydantic and
stamp the ``x-firestore-*`` contract vocabulary; the Rust core does the emit and
the compatibility gate.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from firepact.cli import check_compat, generate_typescript_defs
from firepact.firestore_schema import (
    FirestoreBackfilled,
    FirestoreGeoPoint,
    FirestoreJsonSchema,
    FirestoreRef,
    FirestoreServerTimestamp,
    FirestoreVector,
)
from firepact.firestore_select import (
    RealtimeSpec,
    build_realtime_bundle,
    firestore_realtime,
    registered_roots,
)

try:
    __version__ = version("firepact")
except PackageNotFoundError:  # source checkout without an installed build
    __version__ = "0.0.0+unknown"

__all__ = [
    "FirestoreBackfilled",
    "FirestoreGeoPoint",
    "FirestoreJsonSchema",
    "FirestoreRef",
    "FirestoreServerTimestamp",
    "FirestoreVector",
    "RealtimeSpec",
    "__version__",
    "build_realtime_bundle",
    "check_compat",
    "firestore_realtime",
    "generate_typescript_defs",
    "registered_roots",
]
