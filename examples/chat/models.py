"""Canonical chat example: the Pydantic models behind the golden fixtures.

Backend write convention is ``model_dump(by_alias=True)`` with a camelCase alias
generator (DESIGN.md trap #1); the extractor MUST match it.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from firepact import (
    FirestoreBackfilled,
    FirestoreGeoPoint,
    FirestoreRef,
    FirestoreServerTimestamp,
    firestore_realtime,
)
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model whose wire keys are camelCase (matches the backend serializer)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MessageKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    SYSTEM = "system"


class Profile(CamelModel):
    display_name: str
    avatar_url: str | None


class Reaction(CamelModel):
    emoji: str
    count: int


@firestore_realtime(collection="rooms/{roomId}/messages", id_field="id")
class Message(CamelModel):
    id: str
    author: Annotated[str, FirestoreRef("Profile")]
    author_profile: Profile
    body: Annotated[str, FirestoreBackfilled()]
    created_at: Annotated[datetime, FirestoreServerTimestamp()]
    edited_at: datetime  # plain (non-server) datetime -> Timestamp / Timestamp | Date
    kind: MessageKind
    location: Annotated[tuple[float, float], FirestoreGeoPoint()]  # -> GeoPoint
    metadata: dict[str, str]
    reactions: list[Reaction]
    tags: list[str]
    thumbnail: bytes  # -> Uint8Array
