"""The realtime_app example (production-style): gen-only registration, snake_case
wire, id_field=None, guaranteed= from history, a subcollection, and a dual-context
embedded type. Keeps its two committed outputs from drifting and pins the
datetime -> Timestamp / string distinction that is the whole point of firepact."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any, cast

import pytest
from firepact.cli import (
    build_plain_bundle,
    bundle_for_module,
    emit_plain_typescript,
    emit_shared_typescript,
)
from firepact.firestore_select import _REGISTRY

REPO_ROOT = Path(__file__).resolve().parents[2]
FIRESTORE_TS = REPO_ROOT / "examples" / "gen" / "realtime_app" / "firestore.ts"
DTOS_TS = REPO_ROOT / "examples" / "gen" / "realtime_app" / "dtos.ts"
BUNDLE = REPO_ROOT / "examples" / "gen" / "realtime_app" / "bundle.json"

_ROOTS_MODULE = "examples.gen.realtime_app._fp_roots"
_DTOS_MODULE = "examples.gen.realtime_app.dtos"


def _shared_names() -> list[str]:
    defs = cast("dict[str, Any]", build_plain_bundle(_DTOS_MODULE)["$defs"])
    return sorted(
        n for n, node in defs.items() if isinstance(node, dict) and "enum" in node
    )


def _firestore_bundle() -> dict[str, object]:
    # Register the roots (gen-only module) into the global registry, isolated so
    # the chat example's roots do not leak in.
    saved = dict(_REGISTRY)
    _REGISTRY.clear()
    try:
        mod = importlib.import_module(_ROOTS_MODULE)
        importlib.reload(mod)  # re-fire the firestore_realtime(...) calls
        return bundle_for_module(_ROOTS_MODULE)
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(saved)


def test_realtime_dtos_output_is_current() -> None:
    actual = emit_plain_typescript(build_plain_bundle(_DTOS_MODULE))
    assert DTOS_TS.read_text(encoding="utf-8") == actual


def test_realtime_firestore_output_is_current() -> None:
    actual = emit_shared_typescript(_firestore_bundle(), "./dtos", _shared_names())
    assert FIRESTORE_TS.read_text(encoding="utf-8") == actual


@pytest.mark.skipif(
    bool(os.environ.get("FIREPACT_PYDANTIC_MATRIX")),
    reason="the exact schema-layer bundle is frozen against the locked pydantic",
)
def test_realtime_bundle_is_current() -> None:
    # The committed contract bundle (--bundle-out) matches the model's bundle.
    committed = json.loads(BUNDLE.read_text(encoding="utf-8"))
    assert committed == _firestore_bundle()


def test_chatmessage_is_timestamp_in_firestore_string_over_http() -> None:
    # The dual-context type: Firestore embeds it with a Timestamp; the HTTP DTO
    # serializes the same field as a string. firepact keeps both, distinctly.
    firestore = FIRESTORE_TS.read_text(encoding="utf-8")
    dtos = DTOS_TS.read_text(encoding="utf-8")
    assert "created_at?: Timestamp;" in firestore  # Firestore ChatMessage
    assert "created_at: string;" in dtos  # HTTP ChatMessage
    # ChatMessage is defined in BOTH (not shared); only enums are imported.
    assert "export interface ChatMessage {" in firestore
    assert "export interface ChatMessage {" in dtos
    assert 'import type { ChatStatus, MessageRole } from "./dtos";' in firestore


def test_guaranteed_makes_since_v0_fields_read_required() -> None:
    firestore = FIRESTORE_TS.read_text(encoding="utf-8")
    # handle exists since v0 -> read-required; plan was added in v1 -> read-optional
    # even though it is required in Pydantic (a residual v0 doc lacks it).
    assert "handle: string;" in firestore
    assert "plan?: string;" in firestore
