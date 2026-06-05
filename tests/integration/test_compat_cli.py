"""The compatibility gate is usable from a pip install (native PyO3), not just
the cargo binary: `check_compat` + the `firepact-compat` CLI (`compat_main`)."""

from __future__ import annotations

from pathlib import Path

from firepact import check_compat
from firepact.cli import compat_main

V1 = '{"$defs":{"Doc":{"type":"object","properties":{"a":{"type":"string"}},"required":["a"]}}}'
# additive read-optional field -> compatible
V2_SAFE = '{"$defs":{"Doc":{"type":"object","properties":{"a":{"type":"string"},"b":{"type":"string"}},"required":["a","b"]}}}'
# field removed -> breaking
V2_BREAKING = '{"$defs":{"Doc":{"type":"object","properties":{},"required":[]}}}'


def test_check_compat_flags_breaking() -> None:
    # given / when
    findings = check_compat(V1, V2_BREAKING)

    # then
    assert any(f["verdict"] == "BREAKING" for f in findings)


def test_check_compat_safe_change_has_no_breaking() -> None:
    # given / when
    findings = check_compat(V1, V2_SAFE)

    # then
    assert all(f["verdict"] != "BREAKING" for f in findings)


def test_compat_main_two_arg_exit_codes(tmp_path: Path) -> None:
    # given
    old = tmp_path / "v1.json"
    old.write_text(V1, encoding="utf-8")
    safe = tmp_path / "safe.json"
    safe.write_text(V2_SAFE, encoding="utf-8")
    breaking = tmp_path / "breaking.json"
    breaking.write_text(V2_BREAKING, encoding="utf-8")

    # when / then
    assert compat_main([str(old), str(safe)]) == 0
    assert compat_main([str(old), str(breaking)]) == 1


def test_compat_main_history_form(tmp_path: Path) -> None:
    # given a history dir + a breaking new bundle
    hist = tmp_path / "schemas"
    hist.mkdir()
    (hist / "v1.json").write_text(V1, encoding="utf-8")
    new = tmp_path / "new.json"
    new.write_text(V2_BREAKING, encoding="utf-8")

    # when / then
    assert compat_main(["--history", str(hist), "--new", str(new)]) == 1
