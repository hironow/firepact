"""`firepact-gen --bundle-out` exports the deterministic contract bundle, which
is the artifact committed to schemas/ and fed to `firepact compat`."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from firepact.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_GOLDEN = REPO_ROOT / "fixtures" / "message.bundle.json"


@pytest.mark.skipif(
    bool(os.environ.get("FIREPACT_PYDANTIC_MATRIX")),
    reason="exact schema-layer bundle is frozen against the locked pydantic "
    "(e.g. 2.9 emits enum alongside const for Literal); the matrix checks the "
    "emit-layer golden, which is version-robust",
)
def test_bundle_out_writes_the_contract_bundle(tmp_path: Path) -> None:
    # given
    out = tmp_path / "bundle.json"

    # when
    code = main(["--module", "examples.gen.chat.models", "--bundle-out", str(out)])

    # then
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(
        BUNDLE_GOLDEN.read_text(encoding="utf-8")
    )


def test_bundle_out_is_deterministic(tmp_path: Path) -> None:
    # given / when
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    main(["--module", "examples.gen.chat.models", "--bundle-out", str(a)])
    main(["--module", "examples.gen.chat.models", "--bundle-out", str(b)])

    # then byte-identical (stable for git diffs and the compat gate)
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")
