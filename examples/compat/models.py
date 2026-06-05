"""Compat example: a tiny Firestore document whose schema evolves across releases.

The committed bundles in ``schemas/`` are this model's past released contracts
(``account.v0.json``, ``account.v1.json``); ``just example-compat`` diffs the
*current* model against that whole history with the FULL_TRANSITIVE gate. Adding
the optional ``display_name`` (v0 -> v1) is a SAFE change, so the gate stays
green; removing a field or tightening one would be reported as BREAKING.
"""

from __future__ import annotations

from datetime import datetime

from firepact import firestore_realtime
from pydantic import BaseModel


@firestore_realtime(collection="accounts", id_field=None)
class Account(BaseModel):
    id: str
    created_at: datetime  # Firestore field datetime -> Timestamp (read)
    version: int
    email: str
    display_name: str | None = None  # added in v1 (optional) -> SAFE addition
