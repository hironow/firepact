"""Production Firestore document models -- plain ``BaseModel``, snake_case wire,
and NO firepact import.

This is exactly how a real repository layer looks: the models know nothing about
firepact (it is a dev/gen-only dependency, kept out of the production import
path). firepact registration happens separately in ``_fp_roots.py`` via the
decorator-applied-as-a-function, so these classes are never modified.

``id`` is a stored field that mirrors the document path id (``id_field=None`` in
the registration), not a stripped doc-id. ``__current_version__`` / the
``_migrate_*`` history determines which fields are *guaranteed* (present since the
collection's first version) -- see ``_fp_roots.py``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .dtos import ChatMessage, ChatStatus


class User(BaseModel):
    __collection__ = "users"
    __current_version__ = 2  # v0: id/created_at/updated_at/version/handle; v1: +plan

    id: str
    # A plain datetime in a Firestore document -> Timestamp on read,
    # `Timestamp | Date` on write (see firestore.ts). Inside Firestore this value
    # is a real Timestamp object, NOT an ISO string.
    created_at: datetime
    updated_at: datetime
    version: int
    handle: str  # since v0 -> guaranteed (read-required)
    plan: str  # added in v1 -> read-OPTIONAL (a residual v0 doc lacks it)
    display_name: str | None = None  # optional regardless


class Chat(BaseModel):
    # Stored under users/{userId}/chats (a subcollection); the registration uses
    # the templated path "users/{userId}/chats".
    __collection__ = "chats"
    __current_version__ = 1

    id: str
    created_at: datetime
    updated_at: datetime
    version: int
    status: ChatStatus
    messages: list[ChatMessage]  # embedded; Firestore stores created_at as Timestamp
