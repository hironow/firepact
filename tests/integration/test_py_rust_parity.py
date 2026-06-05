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

# Both front-ends must exist: the native PyO3 module (maturin) AND the cargo
# binary. Skip the whole module if either is missing (e.g. a pip-only install, or
# a pytest run that didn't `cargo build`); a CI job that has both runs it.
_core = pytest.importorskip("firepact._core")
try:
    _BIN = find_binary()
except FileNotFoundError:
    pytest.skip("firepact binary not built (cargo build)", allow_module_level=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = REPO_ROOT / "examples"
# Every committed example contract bundle feeds both front-ends (the exact bytes,
# so no registry is needed). Covering all of them makes the example artifacts
# rust<->py verified, not just the chat one.
GEN_BUNDLES = {
    "chat": (EXAMPLES / "gen" / "chat" / "bundle.json").read_text(encoding="utf-8"),
    "realtime_app": (EXAMPLES / "gen" / "realtime_app" / "bundle.json").read_text(
        encoding="utf-8"
    ),
}
CHAT_BUNDLE = GEN_BUNDLES["chat"]
SCHEMAS = EXAMPLES / "compat" / "schemas"


def _binary(args: list[str], stdin: str | None = None) -> str:
    result = subprocess.run(
        [_BIN, *args],
        input=stdin.encode("utf-8") if stdin is not None else None,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8")


@pytest.mark.parametrize("bundle", GEN_BUNDLES.values(), ids=list(GEN_BUNDLES))
def test_emit_parity(bundle: str) -> None:
    assert _core.emit(bundle) == _binary(["emit", "-"], stdin=bundle)


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
