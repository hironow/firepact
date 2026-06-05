"""Plain HTTP DTOs and the shared enums -- the single source for both layers.

This mirrors a real app's ``app_types``-style module: request/response payloads
whose ``datetime`` is an ISO **string** over HTTP (NOT a Firestore ``Timestamp``),
plus the enums that the Firestore document models also use. Generated with
``firepact-gen --plain`` (datetime -> string, one interface per model).

``ChatMessage`` here is *dual-context*: the same logical shape is embedded in the
Firestore ``Chat`` document (where ``created_at`` is a ``Timestamp``) and returned
over HTTP (where it is a ``string``). It is therefore NOT shared across the two
generated files -- each keeps its own correct definition. Only the enums (which
are context-independent) are shared via ``--shared-from``.

Wire keys are snake_case (plain ``BaseModel``, no alias generator), matching a
backend that writes ``model_dump()`` without an alias generator (DESIGN trap #1).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class MessageRole(StrEnum):
    user = "user"
    assistant = "assistant"


class ChatStatus(StrEnum):
    active = "active"
    archived = "archived"


class ChatMessage(BaseModel):
    id: str
    role: MessageRole
    text: str
    created_at: datetime  # ISO 8601 string over HTTP (a Timestamp inside Firestore)


class PostMessageRequest(BaseModel):
    role: MessageRole
    text: str


class GetChatResponse(BaseModel):
    id: str
    status: ChatStatus
    messages: list[ChatMessage]
    fetched_at: datetime  # ISO 8601 string over HTTP
