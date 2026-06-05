"""Cross-file single source: emit_shared_typescript imports named types from a
sibling module instead of redefining them."""

from __future__ import annotations

from pathlib import Path

from firepact.cli import emit_shared_typescript, main

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


def test_shared_from_derives_names_from_the_module(tmp_path: Path) -> None:
    # --shared-from derives the shared set from the dtos module's own output, so
    # MessageKind (shared) is imported from ./dtos without a hand-maintained list.
    out = tmp_path / "fs.ts"
    code = main(
        [
            "--module",
            "examples.gen.chat.models",
            "--output",
            str(out),
            "--shared",
            "./dtos",
            "--shared-from",
            "examples.gen.chat.dtos",
        ]
    )
    assert code == 0
    txt = out.read_text(encoding="utf-8")
    assert 'import type { MessageKind } from "./dtos";' in txt  # enum auto-shared
    assert "export type MessageKind =" not in txt
    # Only enums are auto-shared: a plain OBJECT defined by the dtos module is
    # never imported (it may be dual-context), so it is not pulled from ./dtos.
    assert "SendMessageRequest" not in txt
