"""Full extractor -> bundle -> firepact -> TypeScript chain matches the goldens.

The example is the worked reference for the real layered pattern: plain HTTP DTOs
(``dtos.ts``) are the single source for shared enums, and the Firestore docs
(``generated.ts``) import them via ``--shared-from`` (names derived from the dtos
module, not a hand-maintained list). The low-level emit golden lives in fixtures/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from firepact import build_realtime_bundle
from firepact.cli import (
    build_plain_bundle,
    bundle_for_module,
    emit_plain_typescript,
    emit_shared_typescript,
    emit_typescript,
)

import examples.gen.chat.models  # noqa: F401  (import fires @firestore_realtime)

REPO_ROOT = Path(__file__).resolve().parents[2]
TS_GOLDEN = REPO_ROOT / "fixtures" / "message.generated.ts"
BUNDLE_GOLDEN = REPO_ROOT / "fixtures" / "message.bundle.json"
EXAMPLE_TS = REPO_ROOT / "examples" / "gen" / "chat" / "generated.ts"
EXAMPLE_DTOS = REPO_ROOT / "examples" / "gen" / "chat" / "dtos.ts"
EXAMPLE_BUNDLE = REPO_ROOT / "examples" / "gen" / "chat" / "bundle.json"

_DTOS_MODULE = "examples.gen.chat.dtos"


def _shared_names() -> list[str]:
    """The shared set the example derives from the dtos module (`--shared-from`):
    only enums are auto-shared (context-independent), mirroring the CLI."""
    defs = cast("dict[str, Any]", build_plain_bundle(_DTOS_MODULE)["$defs"])
    return sorted(
        n for n, node in defs.items() if isinstance(node, dict) and "enum" in node
    )


def test_emit_chain_reproduces_typescript_golden() -> None:
    # the fixtures/ golden is the low-level emit (no shared import)
    assert emit_typescript(build_realtime_bundle()) == TS_GOLDEN.read_text(
        encoding="utf-8"
    )


def test_example_dtos_output_is_current() -> None:
    # plain DTOs (datetime -> string, single source for shared enums)
    actual = emit_plain_typescript(build_plain_bundle(_DTOS_MODULE))
    assert EXAMPLE_DTOS.read_text(encoding="utf-8") == actual


def test_example_firestore_output_is_current() -> None:
    # Firestore docs import the shared types from ./dtos (names derived, not listed)
    actual = emit_shared_typescript(build_realtime_bundle(), "./dtos", _shared_names())
    assert EXAMPLE_TS.read_text(encoding="utf-8") == actual


def test_example_shares_messagekind_not_redefines_it() -> None:
    # MessageKind is defined once (in dtos.ts) and imported by generated.ts
    dtos = EXAMPLE_DTOS.read_text(encoding="utf-8")
    gen = EXAMPLE_TS.read_text(encoding="utf-8")
    assert "export type MessageKind =" in dtos
    assert 'import type { MessageKind } from "./dtos";' in gen
    assert "export type MessageKind =" not in gen


def test_cli_module_path_produces_same_bundle() -> None:
    assert bundle_for_module("examples.gen.chat.models") == build_realtime_bundle()


def test_example_bundle_matches_fixture_golden() -> None:
    # The example commits its contract bundle (--bundle-out) alongside the TS; it
    # is the same artifact as the emit golden's bundle. Static file comparison, so
    # it is robust across the pydantic matrix (neither file is regenerated here).
    assert EXAMPLE_BUNDLE.read_text(encoding="utf-8") == BUNDLE_GOLDEN.read_text(
        encoding="utf-8"
    )
