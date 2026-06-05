"""Selective opt-in (``@firestore_realtime``) and contract bundle assembly.

The transitive closure (nested models, enums) is expanded by Pydantic for free
via ``models_json_schema``; the type graph is never walked by hand. Only roots
receive the realtime metadata (collection + doc-id field).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from firepact.firestore_schema import FirestoreJsonSchema

ModelT = TypeVar("ModelT", bound=type[BaseModel])

_SERIALIZATION: Literal["serialization"] = "serialization"


@dataclass(frozen=True)
class RealtimeSpec:
    collection: str
    id_field: str | None = "id"


_REGISTRY: dict[type[BaseModel], RealtimeSpec] = {}


def firestore_realtime(
    *, collection: str, id_field: str | None = "id"
) -> Callable[[ModelT], ModelT]:
    """Mark a model as a realtime root subscribed via ``onSnapshot``."""

    def deco(cls: ModelT) -> ModelT:
        _REGISTRY[cls] = RealtimeSpec(collection, id_field)
        return cls

    return deco


def registered_roots() -> dict[type[BaseModel], RealtimeSpec]:
    """The realtime roots collected so far (import side effects populate this)."""
    return dict(_REGISTRY)


def build_realtime_bundle() -> dict[str, Any]:
    """Assemble the single enriched JSON Schema 2020-12 bundle (the contract artifact).

    ``by_alias=True`` MUST match the backend's write serialization (DESIGN.md
    trap #1); a mismatch silently makes every field undefined at runtime.
    """
    roots = list(_REGISTRY)
    keyed = [(model, _SERIALIZATION) for model in roots]
    keymap, bundle = models_json_schema(
        keyed,
        schema_generator=FirestoreJsonSchema,
        by_alias=True,
        ref_template="#/$defs/{model}",
    )
    defs: dict[str, Any] = bundle.get("$defs", {})
    for cls, spec in _REGISTRY.items():
        ref = keymap.get((cls, _SERIALIZATION), {}).get("$ref", "")
        name = ref.rsplit("/", 1)[-1]
        node = defs.get(name)
        if node is not None:
            node["x-firestore-collection"] = spec.collection
            if spec.id_field:
                node["x-firestore-doc-id-field"] = spec.id_field
    return bundle
