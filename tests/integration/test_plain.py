"""Plain mode (`firepact-gen --plain`): standard Pydantic -> TS for non-Firestore
DTOs, replacing the legacy pydantic2ts plain output."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from firepact.cli import build_plain_bundle, emit_plain_typescript
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema


class _Dto(BaseModel):
    id: str
    timestamp: datetime  # plain (no Firestore annotation) -> ISO string
    note: str | None = None


def _plain_bundle() -> dict[str, Any]:
    _keymap, bundle = models_json_schema(
        [(_Dto, "serialization")],
        by_alias=True,
        ref_template="#/$defs/{model}",
    )
    return bundle


def test_plain_emit_maps_datetime_to_string() -> None:
    # given / when
    ts = emit_plain_typescript(_plain_bundle())

    # then: single interface, datetime -> string, optional default, no Firestore
    assert "export interface _Dto {" in ts
    assert "id: string;" in ts
    assert "timestamp: string;" in ts
    assert "note?: string | null;" in ts
    assert "Timestamp" not in ts
    assert "firebase/firestore" not in ts


def test_build_plain_bundle_collects_module_models() -> None:
    # given / when: the example module defines Message/Profile/Reaction/MessageKind
    defs = cast(
        "dict[str, Any]", build_plain_bundle("examples.gen.chat.models")["$defs"]
    )

    # then: every model defined in the module is present (not just realtime roots)
    for name in ("Message", "Profile", "Reaction", "MessageKind"):
        assert name in defs, f"{name} missing from plain bundle: {sorted(defs)}"
