"""Command-line entry point: import models, build the bundle, emit TypeScript.

Phase 0 pipes the enriched bundle to the cargo-built ``firepact`` binary over
stdin (no temp file). Phase 0e replaces this subprocess hop with a PyO3-native
call while keeping this CLI surface stable.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from firepact.firestore_select import build_realtime_bundle

# A dotted Python module path: identifiers separated by dots, nothing else.
_MODULE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*")

# `firepact-compat <old.json> <new.json>` takes exactly two positional paths.
_PAIRWISE_ARGC = 2


def find_binary() -> str:
    """Locate the ``firepact`` Rust binary.

    Order: explicit ``FIREPACT_BIN`` override, then the repo-local cargo target
    (debug before release: the dev default is ``cargo build``), then ``PATH``.
    The repo-local build is preferred over PATH so an older globally-installed
    ``firepact`` cannot silently generate stale output during development.
    """
    override = os.environ.get("FIREPACT_BIN")
    if override:
        return override
    repo_root = Path(__file__).resolve().parents[2]
    for profile in ("debug", "release"):
        candidate = repo_root / "target" / profile / "firepact"
        if candidate.exists():
            return str(candidate)
    on_path = shutil.which("firepact")
    if on_path:
        return on_path
    msg = "firepact binary not found (set FIREPACT_BIN, add to PATH, or `cargo build`)"
    raise FileNotFoundError(msg)


def bundle_for_module(module: str) -> dict[str, object]:
    """Import ``module`` (firing ``@firestore_realtime``) and assemble the bundle.

    ``module`` is a developer-supplied build-time argument pointing at their own
    Pydantic models (the same ``--module`` contract as the prior tool). It is
    validated to be a plain dotted module path before import, rejecting anything
    that is not a sequence of identifiers.
    """
    if not _MODULE_NAME.fullmatch(module):
        msg = f"invalid module path: {module!r}"
        raise ValueError(msg)
    # Console scripts do not put cwd on sys.path (unlike `python -m`); add it so
    # `--module pkg.models` resolves against the project the user runs from.
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    importlib.import_module(module)
    return build_realtime_bundle()


def emit_typescript(bundle: dict[str, object]) -> str:
    """Emit TypeScript from the bundle, preferring the native PyO3 module.

    Falls back to the ``firepact`` binary over stdin when the compiled extension
    is not present (e.g. a plain ``cargo build`` checkout without maturin).
    """
    payload = json.dumps(bundle)
    try:
        from firepact import _core
    except ImportError:
        result = subprocess.run(
            [find_binary(), "emit", "-"],
            input=payload.encode("utf-8"),
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8")
    emitted: str = _core.emit(payload)
    return emitted


def emit_shared_typescript(
    bundle: dict[str, object], shared_path: str, shared_names: list[str]
) -> str:
    """Emit TypeScript where ``shared_names`` are imported from ``shared_path``
    (a TS module specifier relative to the output) instead of redefined."""
    payload = json.dumps(bundle)
    try:
        from firepact import _core
    except ImportError:
        result = subprocess.run(
            [
                find_binary(),
                "emit",
                "--shared",
                shared_path,
                "--shared-names",
                ",".join(shared_names),
                "-",
            ],
            input=payload.encode("utf-8"),
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8")
    emitted: str = _core.emit_shared(payload, shared_path, shared_names)
    return emitted


def generate_typescript_defs(module: str, output: str | None = None) -> str:
    """Import ``module``, build the bundle, emit TypeScript (prior-tool-compatible API)."""
    typescript = emit_typescript(bundle_for_module(module))
    if output is not None:
        Path(output).write_text(typescript, encoding="utf-8")
    return typescript


def build_plain_bundle(module: str) -> dict[str, object]:
    """Import ``module`` and build a STANDARD JSON Schema bundle for plain DTOs.

    Unlike :func:`bundle_for_module`, this uses the default schema generator (no
    ``x-firestore-*`` stamping, so ``datetime`` -> ISO string) and collects every
    Pydantic model defined in the module (the realtime registry is not used). It
    replaces the legacy ``pydantic2ts`` plain output.
    """
    from pydantic import BaseModel
    from pydantic.json_schema import models_json_schema

    if not _MODULE_NAME.fullmatch(module):
        msg = f"invalid module path: {module!r}"
        raise ValueError(msg)
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    mod = importlib.import_module(module)
    # Only models DEFINED in this module (not imported bases / external models).
    models = [
        obj
        for obj in vars(mod).values()
        if isinstance(obj, type)
        and issubclass(obj, BaseModel)
        and obj is not BaseModel
        and obj.__module__ == mod.__name__
    ]
    _keymap, bundle = models_json_schema(
        [(m, "serialization") for m in models],
        by_alias=True,
        ref_template="#/$defs/{model}",
    )
    return bundle


def emit_plain_typescript(bundle: dict[str, object]) -> str:
    """Emit plain DTO TypeScript, preferring the native module (binary fallback)."""
    payload = json.dumps(bundle)
    try:
        from firepact import _core
    except ImportError:
        result = subprocess.run(
            [find_binary(), "emit", "--plain", "-"],
            input=payload.encode("utf-8"),
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8")
    emitted: str = _core.emit_plain(payload)
    return emitted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="firepact-gen",
        description="Generate Firestore TypeScript from Pydantic models.",
    )
    parser.add_argument(
        "--module",
        "-m",
        required=True,
        help="Python module that declares @firestore_realtime roots.",
    )
    parser.add_argument(
        "--output", "-o", help="Write TypeScript here (default: stdout)."
    )
    parser.add_argument(
        "--bundle-out",
        help="Write the deterministic contract bundle JSON here (for schemas/ + compat).",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Plain DTO mode: every model in the module, datetime -> string, no "
        "Firestore views (replaces the legacy pydantic2ts plain output).",
    )
    parser.add_argument(
        "--shared",
        help="TS module specifier (relative to --output) to IMPORT --shared-names "
        "from instead of redefining them (cross-file single source).",
    )
    parser.add_argument(
        "--shared-names",
        default="",
        help="Comma-separated type names to import from --shared (e.g. shared enums).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Accepted for prior-tool compatibility (no-op).",
    )
    args = parser.parse_args(argv)

    if args.plain:
        typescript = emit_plain_typescript(build_plain_bundle(args.module))
        if args.output:
            Path(args.output).write_text(typescript, encoding="utf-8")
        else:
            sys.stdout.write(typescript)
        return 0

    bundle = bundle_for_module(args.module)

    if args.bundle_out:
        # sort_keys for a stable artifact: git-friendly and so the compat gate
        # never false-positives on ordering.
        Path(args.bundle_out).write_text(
            json.dumps(bundle, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if args.shared:
        names = [n for n in args.shared_names.split(",") if n]
        typescript = emit_shared_typescript(bundle, args.shared, names)
    else:
        typescript = emit_typescript(bundle)

    if args.output:
        Path(args.output).write_text(typescript, encoding="utf-8")
    elif not args.bundle_out:
        sys.stdout.write(typescript)
    return 0


# --- compatibility gate (usable from a pip install, no cargo binary needed) ---


def _eprint(message: str) -> None:
    sys.stderr.write(message + "\n")


def check_compat(old_json: str, new_json: str) -> list[dict[str, Any]]:
    """Diff two contract bundles, returning structured findings.

    Each finding is ``{"def", "field"|None, "verdict": "SAFE"|"BREAKING",
    "message"}``. Requires the native module (built by maturin / `pip install`).
    """
    from firepact import _core

    findings: list[dict[str, Any]] = json.loads(_core.compat(old_json, new_json))
    return findings


def _report(label: str, findings: list[dict[str, Any]]) -> None:
    for f in findings:
        loc = f["def"] if f["field"] is None else f"{f['def']}.{f['field']}"
        _eprint(f"[{label}] {f['verdict']:8} {loc} {f['message']}")


def _history_files(directory: str) -> list[Path]:
    return sorted(Path(directory).glob("*.json"))


def _compat_history(history_dir: str, new_path: str) -> int:
    new_text = Path(new_path).read_text(encoding="utf-8")
    new_resolved = Path(new_path).resolve()
    any_breaking = False
    compared = 0
    for past in _history_files(history_dir):
        if past.resolve() == new_resolved:
            continue  # don't diff --new against itself
        compared += 1
        findings = check_compat(past.read_text(encoding="utf-8"), new_text)
        _report(past.name, findings)
        any_breaking |= any(f["verdict"] == "BREAKING" for f in findings)
    if any_breaking:
        _eprint("compat: BREAKING against at least one past version")
        return 1
    _eprint(f"compat: compatible with all {compared} past version(s)")
    return 0


def compat_main(argv: list[str] | None = None) -> int:
    raw = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(
        prog="firepact-compat",
        description="FULL_TRANSITIVE Firestore contract compatibility gate.",
    )
    parser.add_argument("paths", nargs="*", help="<old.json> <new.json>")
    parser.add_argument("--history", help="Directory of committed past *.json bundles.")
    parser.add_argument("--new", dest="new_path", help="New bundle (with --history).")
    args = parser.parse_args(raw)

    try:
        from firepact import _core  # noqa: F401 - probe the native module
    except ImportError:
        # Dev fallback: delegate to the firepact binary (a pip install has _core).
        return subprocess.run([find_binary(), "compat", *raw], check=False).returncode

    if args.history and args.new_path:
        return _compat_history(args.history, args.new_path)
    if len(args.paths) == _PAIRWISE_ARGC:
        findings = check_compat(
            Path(args.paths[0]).read_text(encoding="utf-8"),
            Path(args.paths[1]).read_text(encoding="utf-8"),
        )
        _report("compat", findings)
        if any(f["verdict"] == "BREAKING" for f in findings):
            _eprint("compat: BREAKING changes detected")
            return 1
        _eprint("compat: compatible")
        return 0
    # argparse error() raises SystemExit, so this never falls through.
    parser.error("expected <old.json> <new.json> or --history <dir> --new <file>")


if __name__ == "__main__":
    raise SystemExit(main())
