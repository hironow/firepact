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

from firepact.firestore_select import build_realtime_bundle

# A dotted Python module path: identifiers separated by dots, nothing else.
_MODULE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*")


def find_binary() -> str:
    """Locate the ``firepact`` Rust binary: env override, PATH, then cargo target."""
    override = os.environ.get("FIREPACT_BIN")
    if override:
        return override
    on_path = shutil.which("firepact")
    if on_path:
        return on_path
    repo_root = Path(__file__).resolve().parents[2]
    for profile in ("release", "debug"):
        candidate = repo_root / "target" / profile / "firepact"
        if candidate.exists():
            return str(candidate)
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
    importlib.import_module(module)
    return build_realtime_bundle()


def emit_typescript(bundle: dict[str, object]) -> str:
    """Pipe the bundle through ``firepact emit`` and return the generated TypeScript."""
    payload = json.dumps(bundle).encode("utf-8")
    result = subprocess.run(
        [find_binary(), "emit", "-"],
        input=payload,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8")


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
        "--exclude",
        action="append",
        default=[],
        help="Accepted for prior-tool compatibility (no-op).",
    )
    args = parser.parse_args(argv)

    bundle = bundle_for_module(args.module)
    typescript = emit_typescript(bundle)

    if args.output:
        Path(args.output).write_text(typescript, encoding="utf-8")
    else:
        sys.stdout.write(typescript)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
