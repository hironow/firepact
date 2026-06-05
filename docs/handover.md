# Handover

**Last updated:** 2026-06-06 (JST)
**Updated by:** claude

## Current State

All phases (0 -> 1 -> 3 -> 2) are implemented and green.

- **Phase 0 (shippable)**: Rust emitter (wire types, read/write/update projection,
  open string enums, doc-id converter, typed path helpers); Python extractor
  (Pydantic-delegated bundle, `x-firestore-*`, `by_alias=True` guard); maturin/
  PyO3 wheel with native `emit` + console scripts + `generate_typescript_defs`;
  real-emulator E2E (write -> generate -> `tsc` -> `onSnapshot` read).
- **Phase 1**: `firepact compat` FULL_TRANSITIVE gate. The HANDOFF S5.2 taxonomy
  is a passing test table; two CLI forms (pairwise and `--history`). ADR 0004.
- **Phase 3**: CI (rust + python 3.11-3.13 + pydantic drift matrix + tsc) and
  dependency updates via Dependabot (github-actions, cargo, uv, npm; a 7-day
  cooldown holds back fresh releases, security updates excepted -- replaced
  Renovate). The 2-layer "snapshot" is the committed golden pair (schema-layer
  `message.bundle.json` + emit-layer `message.generated.ts`), compared in tests.
- **Phase 2**: tuples (prefixItems), discriminated unions (oneOf, narrowable),
  update view (`UpdateData<Write>`), typed path helpers.
- **Distribution**: the compat gate is exposed to pip installs via PyO3 + the
  `firepact-compat` console script (not just the cargo binary). `firepact-gen
  --bundle-out` exports the contract bundle; `examples/compat/schemas/` + `just
  example-compat` + a CI compat job gate the example contract. Wheels are abi3
  (`abi3-py311`): one stable-ABI wheel per platform covers CPython 3.11+, so the
  release matrix is 5 wheels + sdist (not per-version). pyo3 is on 0.28.
- Wire-type coverage: ALL Firestore value types -- string, number, boolean,
  null, map, array, timestamp (server/plain), GeoPoint, bytes (`Bytes`),
  reference, and Vector (`VectorValue`) -- plus open enum, tuple, nested model,
  discriminated union. `tests/firestore_field_types.rs` is a forget-guard
  manifest: a new field type cannot ship without emit + golden + E2E coverage.
  The e2e reader runtime-asserts every value type against the live emulator.
- Cross-cutting: ADRs 0001-0013, `.semgrep/` skeleton, published metadata,
  `private/PUBLISH_HOWTO.md` (git-ignored local runbook).
- Runtime E2E has been run green against the live emulator; it caught a real
  wire-type bug (`bytes` -> `Bytes`, not `Uint8Array`, for the client SDK; see
  ADR 0008) that `tsc` could not.

`just test` (rust + python) and `just lint` are green; `just test-e2e` passes
against the running emulator. All commits are Conventional Commits with
structural/behavioral separated.

## In Progress

Nothing. **v0.1.7 is published** to PyPI (`firepact`) and crates.io
(`firepact-core`) via the OIDC trusted-publishing workflow (ADR 0013), with PEP 740
publish attestations (PyPI) and SLSA build provenance (GitHub) verified.

## Next Actions

1. Future releases: bump `pyproject.toml` + `Cargo.toml` together, commit, then
   `git tag vX.Y.Z` + push -> CI builds, you approve the `release` environment, and
   it publishes to both registries tokenlessly. `private/PUBLISH_HOWTO.md` is the
   runbook. The bootstrap (env + `v*` ruleset + read-only token; PyPI pending
   publisher; crates.io TP enforcement) is done.
2. Optionally: start committing released bundles under `schemas/v*.json` and wire
   `firepact compat --history schemas --new <new>` into CI to begin enforcing the
   gate against real history.
3. Grow `.semgrep/rules/` as patterns recur (candidates listed in its README).
4. Dependabot carries action-SHA + dependency bumps (7-day cooldown). Review and
   merge its PRs; prefer merging only releases past the cooldown, and confirm CI is
   green (the combined-bump run on `main` is the authoritative check).

## Review pass (codex + 3 review agents)

A full review was run after implementation. Critical findings were fixed with
regression tests: the compat read signature is now structural (array-of-enum and
nullable-enum retypes, numeric-enum member changes, and root-metadata changes are
caught; union branch order is normalized so reorders are not false breaks); the
read converter strips the doc-id on write; the Python CLI prefers the repo-local
binary; the e2e reader reads the standard `FIRESTORE_EMULATOR_HOST`. Two design
points are accepted-and-documented: the generated converter is **read-oriented**
(writes use `{Name}Write` with setDoc/updateDoc directly, since
FirestoreDataConverter has a single app type), and the global `@firestore_realtime`
registry is correct for the fresh-process CLI but accumulates in long-lived
processes.

## Known Risks / Blockers

- Native extension staleness: `uv sync` skips rebuilding the in-tree PyO3 module
  on same-version Rust edits; `just build-ext` (and `just test-py`/`test-e2e`)
  force `uv sync --reinstall-package firepact`. Run it after changing Rust.
- `python/firepact/cli.py` `importlib.import_module(--module)` is flagged by the
  global semgrep guardrail (false positive: developer build-time input, validated
  to a dotted path, same as the prior tool). Accepted; the tested core API has no
  dynamic import. The managed scanner does not honor inline `# nosemgrep`.
- Python pinned to 3.13 locally for dependency wheels.
- `insta` was not adopted: the 2-layer freeze is realized as committed golden
  artifacts (deterministic, real files consumers use), avoiding duplicate
  assertions. Revisit if a richer snapshot-review workflow is wanted.
- E2E is local-only (needs the emulator + bun); CI does the static `tsc` check.
- Release runners: macOS wheels build on `macos-latest` (Apple Silicon); the Intel
  `macos-13` image was retired 2025-12-04, so x86_64 macOS wheels are cross-compiled
  on the arm64 runner. If x86_64 mac coverage matters past 2027, revisit (Intel
  GitHub runners end Fall 2027).
- Actions allowlist: the repo restricts non-`hironow`/non-GitHub actions to a
  pinned set (`Settings -> Actions -> General`). `extractions/setup-just` pulls
  `extractions/setup-crate` transitively, so BOTH must be allowlisted or CI setup
  fails. Add new third-party actions to the allowlist before using them.

## Context the Next Actor Needs

- Emulator: `127.0.0.1:8080`, project `demo-firepact`, `singleProjectMode`
  (`~/dotfiles/emulator`, assumed running).
- `fixtures/` is the canonical contract artifact (schema + emit layers).
- read-view projection is shared by emit and compat (`read_optional`,
  `read_type_signature` in `src/lib.rs`) so the gate never drifts.

## Relevant Files and Commands

- `src/lib.rs` - emitter + shared projection + PyO3 binding; `src/compat.rs` - gate.
- `src/main.rs` - CLI (`emit`, `compat`).
- `python/firepact/` - extractor; `examples/gen/chat/models.py` - example models.
- `tests/` - golden, cli, open_enum, converter, compat, emit_phase2 (rust);
  unit/integration/e2e (python).
- `docs/` - live docs of the current system: `architecture.md`, `usage.md`,
  `contract.md`, `compatibility.md` (the "what"); `docs/adr/0001-0013` - the "why".
- `just test` / `just lint` / `just test-e2e` / `just build-ext` / `just example-gen`.
