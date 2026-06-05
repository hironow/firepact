# 0012. The Python runtime uses the native module only; the binary is a standalone CLI

**Date:** 2026-06-05
**Status:** Accepted

## Context

`firepact-core` (the Rust engine) is exposed two ways: a PyO3 native extension
(`firepact._core`, built by maturin into the wheel) and a standalone `firepact`
cargo binary. The Python CLI helpers (`emit_typescript`, `emit_plain_typescript`,
`emit_shared_typescript`, `compat_main`) preferred `_core` but **fell back to a
`subprocess` call to the binary** when `_core` failed to import.

That fallback created four overlapping terms for one engine -- "rust",
"subprocess", "pyo3", "native/`_core`" -- and a second runtime code path. It is
also not how comparable Rust-core + Python projects ship in 2026:

- **Native-extension libraries** (polars, pydantic-core, ruff's core,
  cryptography, tokenizers): the Rust core is a `.so`/`.pyd` in the wheel, imported
  in-process. No subprocess, no binary fallback.
- **Standalone CLIs** (uv, ruff's CLI): a single Rust binary, shipped directly or
  as a maturin "bin" wheel script. No PyO3 library API.

Each picks one path per artifact; none maintains a "native, else shell out to a
duplicate binary" fallback. firepact's wheel ships `_core` (not the binary), so
the fallback only ever fired in a `cargo build`-only dev checkout -- a case
`uv sync` / `maturin develop` already covers by building `_core`.

## Decision

The **Python package uses `_core` only**. `emit_typescript`,
`emit_plain_typescript`, `emit_shared_typescript`, and `compat_main` import
`_core` and call it directly; if `_core` is missing they raise a clear
"run `uv sync` / install the wheel" error rather than silently shelling out.

The **`firepact` cargo binary is a standalone CLI and dev/CI tool**, not a Python
runtime dependency. It backs `just gen-docs` / `just example-compat`, the Rust
CLI tests (`cli.rs`), and the py/rust parity test. `find_binary()` is retained to
locate it for those, but the Python runtime never invokes it.

So the engine is reached exactly two independent ways, with no cross-fallback:

- `firepact._core` -- the native module the Python package imports (in-process);
- `firepact` -- the standalone binary (separate program).

The parity test keeps the two builds of the core byte-identical.

## Consequences

### Positive

- One runtime path for the Python package; the word "subprocess" leaves the
  vocabulary. Matches the polars / pydantic-core norm.
- A missing `_core` is a loud, actionable error instead of a silent binary hop
  that behaves subtly differently (and isn't even present in a pip install).

### Negative

- A `cargo build`-only checkout can no longer run `firepact-gen` via the binary;
  developers must build `_core` (`uv sync` / `maturin develop`). This is the
  documented dev setup already.

### Neutral

- The binary is still built and tested; only its role as a *Python fallback* is
  removed. The py/rust parity test still guards that both stay in lock-step.
