"""Firestore wire-type annotations and the custom JSON Schema generator.

These stamp the ``x-firestore-*`` contract vocabulary (DESIGN.md S4) onto the
Pydantic-generated JSON Schema. The base schema is always obtained from the
handler first, then overridden -- never reconstructed from scratch.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class FirestoreRef:
    """``Annotated[str, FirestoreRef("Profile")]`` -> ``DocumentReference<Profile>``."""

    target: str

    def __get_pydantic_json_schema__(
        self, cs: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        js = handler(cs)
        js["x-firestore-type"] = "reference"
        js["x-firestore-ref-target"] = self.target
        return js


@dataclass(frozen=True)
class FirestoreServerTimestamp:
    """Field written via ``serverTimestamp()``; read view is ``Timestamp | null``."""

    def __get_pydantic_json_schema__(
        self, cs: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        js = handler(cs)
        js["x-firestore-type"] = "timestamp"
        js["x-firestore-server-timestamp"] = True
        return js


@dataclass(frozen=True)
class FirestoreGeoPoint:
    """Geo field stored as a Firestore ``GeoPoint``."""

    def __get_pydantic_json_schema__(
        self, cs: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        js = handler(cs)
        js["x-firestore-type"] = "geopoint"
        return js


@dataclass(frozen=True)
class FirestoreVector:
    """``Annotated[list[float], FirestoreVector()]`` -> Firestore vector (``VectorValue``)."""

    def __get_pydantic_json_schema__(
        self, cs: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        js = handler(cs)
        js["x-firestore-type"] = "vector"
        return js


@dataclass(frozen=True)
class FirestoreBackfilled:
    """Presence guaranteed across all live docs -> the read view may promote to required."""

    since_version: str | None = None

    def __get_pydantic_json_schema__(
        self, cs: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        js = handler(cs)
        js["x-firestore-presence-guaranteed"] = True
        if self.since_version:
            js["x-firestore-presence-since"] = self.since_version
        return js


class FirestoreJsonSchema(GenerateJsonSchema):
    """Stamps wire types that have no 1:1 Python annotation onto base schemas.

    ``int``/``float`` are intentionally left untouched: JSON Schema already
    distinguishes ``integer``/``number`` and the emitter maps both to ``number``.
    """

    def datetime_schema(self, schema: core_schema.DatetimeSchema) -> JsonSchemaValue:
        js = super().datetime_schema(schema)
        js["x-firestore-type"] = "timestamp"
        return js

    def bytes_schema(self, schema: core_schema.BytesSchema) -> JsonSchemaValue:
        js = super().bytes_schema(schema)
        js["x-firestore-type"] = "bytes"
        return js
