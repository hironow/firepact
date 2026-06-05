"""`@firestore_realtime(guaranteed=[...])` marks always-present fields as
read-required without touching the production model (set from a gen-only module).
Everything else stays read-optional (the FULL_TRANSITIVE safe default)."""

from __future__ import annotations

import pytest
from firepact import firestore_realtime
from firepact.cli import emit_typescript
from firepact.firestore_select import _REGISTRY, build_realtime_bundle
from pydantic import BaseModel


def test_guaranteed_fields_are_read_required() -> None:
    saved = dict(_REGISTRY)
    _REGISTRY.clear()
    try:

        @firestore_realtime(collection="docs", id_field=None, guaranteed=["a"])
        class Doc(BaseModel):
            a: str
            b: str

        bundle = build_realtime_bundle()
        props = bundle["$defs"]["Doc"]["properties"]
        assert props["a"]["x-firestore-presence-guaranteed"] is True
        assert "x-firestore-presence-guaranteed" not in props["b"]

        ts = emit_typescript(bundle)
        read = ts.split("export interface Doc {")[1].split("}")[0]
        assert "a: string;" in read  # guaranteed -> read-required
        assert "b?: string;" in read  # not guaranteed -> read-optional
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(saved)


def test_guaranteed_unknown_field_raises() -> None:
    saved = dict(_REGISTRY)
    _REGISTRY.clear()
    try:

        @firestore_realtime(collection="docs", id_field=None, guaranteed=["nope"])
        class Doc(BaseModel):
            a: str

        with pytest.raises(ValueError, match="guaranteed field"):
            build_realtime_bundle()
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(saved)
