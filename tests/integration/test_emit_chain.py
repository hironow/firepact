"""Full extractor -> bundle -> firepact binary -> TypeScript chain matches the
emit-layer golden. Exercises the real subprocess hop (no mocks)."""

from __future__ import annotations

from pathlib import Path

from firepact import build_realtime_bundle
from firepact.cli import bundle_for_module, emit_typescript

import examples.chat.models  # noqa: F401  (import fires @firestore_realtime)

REPO_ROOT = Path(__file__).resolve().parents[2]
TS_GOLDEN = REPO_ROOT / "fixtures" / "message.generated.ts"
EXAMPLE_TS = REPO_ROOT / "examples" / "chat" / "generated.ts"


def test_emit_chain_reproduces_typescript_golden() -> None:
    # given
    expected = TS_GOLDEN.read_text(encoding="utf-8")

    # when
    actual = emit_typescript(build_realtime_bundle())

    # then
    assert actual == expected


def test_committed_example_output_is_current() -> None:
    # The example records the input (models.py) and the final output
    # (generated.ts) as a pair; this keeps the committed .ts from drifting.
    # given / when
    actual = emit_typescript(build_realtime_bundle())

    # then
    assert EXAMPLE_TS.read_text(encoding="utf-8") == actual


def test_cli_module_path_produces_same_bundle() -> None:
    # given / when
    via_cli = bundle_for_module("examples.chat.models")

    # then
    assert via_cli == build_realtime_bundle()
