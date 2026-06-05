"""Command-line entry point: import models, build the bundle, emit TypeScript.

The engine is the Rust core. The Python package reaches it ONLY through the
native PyO3 module ``firepact._core`` (built into the wheel by maturin); there is
no subprocess fallback. The standalone ``firepact`` cargo binary is a separate
CLI / dev-and-test tool (see ADR 0012), not part of this runtime path.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, cast

from firepact.firestore_select import build_realtime_bundle

# A dotted Python module path: identifiers separated by dots, nothing else.
_MODULE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*")

# `firepact-compat <old.json> <new.json>` takes exactly two positional paths.
_PAIRWISE_ARGC = 2


def find_binary() -> str:
    """Locate the standalone ``firepact`` Rust binary.

    For **tests and dev tooling only** (the py/rust parity test, and anything that
    drives the standalone CLI); the Python runtime never calls the binary (ADR
    0012). Order: ``FIREPACT_BIN`` override, then the repo-local cargo target
    (debug before release), then ``PATH``.
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


def _load_core() -> Any:
    """Import the native engine ``firepact._core`` or raise an actionable error.

    The Python package has no binary fallback (ADR 0012): a missing ``_core`` means
    the native module was not built, so say how to build it instead of failing
    obscurely (or silently shelling out to a binary that may be absent).
    """
    try:
        from firepact import _core
    except ImportError as exc:
        msg = (
            "firepact._core (the native engine) is not built. Install the wheel "
            "(`pip install firepact`) or build it for development "
            "(`uv sync` / `maturin develop`)."
        )
        raise ImportError(msg) from exc
    return _core


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
    """Emit TypeScript from the bundle via the native engine (``_core``)."""
    emitted: str = _load_core().emit(json.dumps(bundle))
    return emitted


def emit_shared_typescript(
    bundle: dict[str, object], shared_path: str, shared_names: list[str]
) -> str:
    """Emit TypeScript where ``shared_names`` are imported from ``shared_path``
    (a TS module specifier relative to the output) instead of redefined."""
    emitted: str = _load_core().emit_shared(
        json.dumps(bundle), shared_path, shared_names
    )
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
    """Emit plain DTO TypeScript via the native engine (``_core``)."""
    emitted: str = _load_core().emit_plain(json.dumps(bundle))
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
        help="TS module specifier (relative to --output) to IMPORT shared types "
        "from instead of redefining them (cross-file single source).",
    )
    parser.add_argument(
        "--shared-from",
        help="Python module whose plain-generated types are the shared source. "
        "firepact derives the shared names from it (the types --shared defines), so "
        "no hand-maintained list -- only the ones actually referenced are imported.",
    )
    parser.add_argument(
        "--shared-names",
        default="",
        help="Explicit comma-separated names to import from --shared (added to "
        "anything derived from --shared-from).",
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
        names = {n for n in args.shared_names.split(",") if n}
        if args.shared_from:
            # Derive the shared set from the plain module's own output, so the
            # names come from real Python references (no hand-maintained list) and
            # are guaranteed to exist in --shared. Only ENUMS are auto-shared: they
            # are context-independent, whereas an object can be dual-context (e.g.
            # a datetime is Timestamp in Firestore but string in the DTO), so it
            # must keep its own Firestore definition. Share a pure object explicitly
            # via --shared-names if needed. emit imports only the referenced subset.
            plain_defs = cast(
                "dict[str, Any]",
                build_plain_bundle(args.shared_from).get("$defs", {}),
            )
            names |= {
                name
                for name, node in plain_defs.items()
                if isinstance(node, dict) and "enum" in node
            }
        typescript = emit_shared_typescript(bundle, args.shared, sorted(names))
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
    findings: list[dict[str, Any]] = json.loads(_load_core().compat(old_json, new_json))
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
        _load_core()  # native engine only; no binary fallback (ADR 0012)
    except ImportError as exc:
        _eprint(str(exc))
        return 1

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
