"""Cross-file single source: emit_shared_typescript imports named types from a
sibling module instead of redefining them."""

from __future__ import annotations

from firepact.cli import emit_shared_typescript

_BUNDLE: dict[str, object] = {
    "$defs": {
        "E": {"type": "string", "enum": ["a", "b"]},
        "D": {
            "type": "object",
            "x-firestore-collection": "d",
            "properties": {"id": {"type": "string"}, "e": {"$ref": "#/$defs/E"}},
            "required": ["id", "e"],
        },
    }
}


def test_shared_names_are_imported_not_redefined() -> None:
    ts = emit_shared_typescript(_BUNDLE, "./types", ["E"])
    assert 'import type { E } from "./types";' in ts
    assert "export type E =" not in ts  # imported, not redefined
    assert "export interface D {" in ts  # document still defined


def test_no_shared_names_defines_everything() -> None:
    ts = emit_shared_typescript(_BUNDLE, "./types", [])
    assert "export type E =" in ts  # nothing shared -> defined locally
    assert 'from "./types"' not in ts
