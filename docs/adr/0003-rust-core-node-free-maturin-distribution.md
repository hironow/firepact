# 0003. Rust core, Node-free, distributed via maturin/PyO3

**Date:** 2026-06-05
**Status:** Accepted

## Context

The predecessor (`pydantic-to-typescript`) depended on Node's `json2ts`, which is
the single biggest adoption friction for a Python backend team. The emit/compat
logic is tiny and CPU-trivial (sub-millisecond); the real cost is the Python
import of the target module.

## Decision

Write the core as a Rust crate (`firepact-core`, binary `firepact`) with **no
Node and no Python dependency**. Distribute it via maturin as a PyO3 extension so
`pip install firepact` ships the native `emit`/`compat` plus console scripts
(`pydantic2ts` drop-in, `firepact-gen`) and the `from firepact import
generate_typescript_defs` API. PyO3 is feature-gated (`python`): the `firepact`
binary builds without it and stays Python-free.

Rust is chosen for single-binary distribution, type-driven exhaustiveness, and
WASM portability -- not speed.

## Consequences

### Positive

- Existing users migrate with `pip install` alone; no Node toolchain.
- The pure binary is installable via `cargo install` and embeddable (WASM later).

### Negative

- A mixed Rust/Python build (maturin). `uv sync` skips rebuilding the in-tree
  extension on same-version source edits, so `just build-ext` forces it.

### Neutral

- Phase 0 wired the Python layer to the binary over a subprocess; the native
  PyO3 path replaced it while keeping the subprocess as a fallback.
