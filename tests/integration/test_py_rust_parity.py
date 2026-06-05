"""The native PyO3 module and the cargo binary are two front-ends over the same
Rust core; `emit_typescript` prefers native and falls back to the binary. These
tests pin that the two produce **byte-identical** output, so the fallback can
never silently diverge. Skipped when the native extension is not built."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from firepact.cli import build_plain_bundle, find_binary

_core = pytest.importorskip("firepact._core")

REPO_ROOT = Path(__file__).resolve().parents[2]
# A rich, committed Firestore contract bundle (timestamps, enum, ref, nested,
# vector, geopoint, ...): the exact bytes feed both front-ends, so no registry.
CHAT_BUNDLE = (REPO_ROOT / "examples" / "gen" / "chat" / "bundle.json").read_text(
    encoding="utf-8"
)
SCHEMAS = REPO_ROOT / "examples" / "compat" / "schemas"


def _binary(args: list[str], stdin: str | None = None) -> str:
    result = subprocess.run(
        [find_binary(), *args],
        input=stdin.encode("utf-8") if stdin is not None else None,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8")


def test_emit_parity() -> None:
    assert _core.emit(CHAT_BUNDLE) == _binary(["emit", "-"], stdin=CHAT_BUNDLE)


def test_emit_plain_parity() -> None:
    plain = json.dumps(build_plain_bundle("examples.gen.chat.dtos"))
    assert _core.emit_plain(plain) == _binary(["emit", "--plain", "-"], stdin=plain)


def test_emit_shared_parity() -> None:
    native = _core.emit_shared(CHAT_BUNDLE, "./dtos", ["MessageKind"])
    binary = _binary(
        ["emit", "--shared", "./dtos", "--shared-names", "MessageKind", "-"],
        stdin=CHAT_BUNDLE,
    )
    assert native == binary


def test_compat_parity() -> None:
    old = (SCHEMAS / "account.v0.json").read_text(encoding="utf-8")
    new = (SCHEMAS / "account.v1.json").read_text(encoding="utf-8")
    native = _core.compat(old, new)
    binary = _binary(
        [
            "compat",
            "--json",
            str(SCHEMAS / "account.v0.json"),
            str(SCHEMAS / "account.v1.json"),
        ]
    )
    assert native == binary
