# Handover

**Last updated:** 2026-09-04 13:46 (JST)
**Updated by:** Claude Code session 01LXPmm8VuMHBjo4Q6k7tRtq (delegated by hironow)

## Current State

v0.1.8 is published on PyPI (`firepact`) and crates.io (`firepact-core`) through
OIDC trusted publishing (ADR 0013), and `main` is green. Every planned phase is
implemented: the Rust emitter, the Python extractor, the FULL_TRANSITIVE compat
gate, the CI matrix, and the Phase 2 projections. What the system does is in
[`docs/README.md`](README.md); why it is shaped that way is in [`adr/`](adr/).
Work since the last handover has been maintenance only: Dependabot bumps and a
re-lock of `uv.lock` in the Takumi Guard index form.

Repository hardening lives in GitHub settings, not in the tree:

- **CodeQL default setup — enabled 2026-09-04.** Weekly, default query suite,
  remote threat model, over actions / python / javascript-typescript / rust.
  The first scan has completed.
- **Private vulnerability reporting — enabled 2026-09-04.**
- Already in place: the `release` environment (required reviewer `hironow`, tag
  branch policy), the active `v*` tag ruleset, Dependabot version and security
  updates, and secret scanning with push protection.

## In Progress

Nothing. The eight alerts the first CodeQL scan raised are fixed, and the latest
scan of `main` reports no results.

## Next Actions

1. Work through Dependabot's uv pull requests as they arrive. They resolve again
   now that the cooldown is relative, so the backlog it could not open before
   should show up on its next run.
2. Still open from before: commit released bundles under `schemas/v*.json` and
   wire `firepact compat --history schemas` into CI, and grow `.semgrep/rules/`
   as patterns recur.

## Known Risks / Blockers

- **Re-lock only under the Takumi Guard index.** CI injects
  `UV_INDEX_URL=https://pypi.flatt.tech/simple/`, so a lockfile resolved against
  pythonhosted URLs fails `uv sync --locked`. Export that variable before
  `uv lock`.
- `uv sync` skips rebuilding the in-tree PyO3 module when Rust changes without a
  version bump. Run `just build-ext` after touching Rust.
- The `importlib.import_module` call in `python/firepact/cli.py` trips the managed
  semgrep guardrail. Accepted false positive: a validated dotted path from
  build-time developer input, and that scanner ignores inline `# nosemgrep`.
- x86_64 macOS wheels are cross-compiled on the arm64 runner, the Intel image
  having been retired. Revisit if that coverage matters past 2027.

## Context the Next Actor Needs

- `main` is covered by the `protect` ruleset: pull requests only, squash merges
  only, linear history, required checks, and no bypass for anyone.
- `[tool.uv] exclude-newer` is a seven-day cooldown, not a date to maintain. uv
  records the span in `uv.lock` and recomputes it only on a new resolution, so
  `just deps-upgrade` is the only lever.
- Nine `v*` tags exist and no GitHub Release has been cut against any of them.
  That is deliberate; the registries are the release surface.
- E2E is local-only: it needs bun and the Firestore emulator on `127.0.0.1:8080`,
  project `demo-firepact`, `singleProjectMode`, from `~/dotfiles/emulator`. The
  CI e2e job runs it under `firebase emulators:exec`.
- `fixtures/` holds the canonical contract artifact, and the read-view projection
  is shared by emit and compat in `src/lib.rs`, so the gate cannot drift.
- Releasing has its own document, [`docs/release.md`](release.md): the repository rules, the
  tag-driven workflow, and the checks to run first.
- Third-party actions must be allowlisted under Settings, Actions, General.
  `extractions/setup-just` pulls in `extractions/setup-crate`, so both need an
  entry before CI setup will run.

## Relevant Files and Commands

- `.github/workflows/ci.yaml` — the CI gate; declares `permissions: contents: read`.
- [`docs/release.md`](release.md) — how a version reaches PyPI and crates.io.
- `pyproject.toml`, key `[tool.uv] exclude-newer` — the dependency cooldown.
- `src/lib.rs` — emitter, shared projection, PyO3 binding; `src/compat.rs` — gate.
- `just check` — the no-write gate: rust and python lint, types, markdown, links.
- `just test` / `just test-e2e` / `just build-ext` / `just deps-upgrade`.
- `just ci` — local CI parity; `just ci-all` adds the pydantic version matrix.
