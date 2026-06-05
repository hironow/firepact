"""Plain HTTP DTOs for the chat example (request/response payloads).

These are NOT Firestore documents: their `datetime` is an ISO **string** over
HTTP, not a Firestore `Timestamp`. They are generated with `firepact-gen --plain`
(datetime -> string, one plain interface per model). `MessageKind` is shared with
the Firestore `Message`; it is defined here (the plain layer is the single source)
and imported by the Firestore output via `--shared`.
"""

from __future__ import annotations

from datetime import datetime

from .models import CamelModel, MessageKind


class SendMessageRequest(CamelModel):
    kind: MessageKind
    body: str
    client_time: datetime  # ISO 8601 string over HTTP (NOT a Firestore Timestamp)


class SendMessageResponse(CamelModel):
    id: str
    accepted_at: datetime  # ISO 8601 string over HTTP
