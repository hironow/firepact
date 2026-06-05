"""firepact: Firestore-aware Pydantic -> TypeScript contract extractor.

The Python layer's only job is to delegate schema generation to Pydantic and
stamp the ``x-firestore-*`` contract vocabulary; the Rust core does the emit and
the compatibility gate.
"""

from __future__ import annotations

from firepact.cli import generate_typescript_defs
from firepact.firestore_schema import (
    FirestoreBackfilled,
    FirestoreGeoPoint,
    FirestoreJsonSchema,
    FirestoreRef,
    FirestoreServerTimestamp,
)
from firepact.firestore_select import (
    RealtimeSpec,
    build_realtime_bundle,
    firestore_realtime,
    registered_roots,
)

__version__ = "0.1.0"

__all__ = [
    "FirestoreBackfilled",
    "FirestoreGeoPoint",
    "FirestoreJsonSchema",
    "FirestoreRef",
    "FirestoreServerTimestamp",
    "RealtimeSpec",
    "__version__",
    "build_realtime_bundle",
    "firestore_realtime",
    "generate_typescript_defs",
    "registered_roots",
]
