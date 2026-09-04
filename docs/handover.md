# Handover

**Last updated:** 2026-09-04 20:19 (JST)
**Updated by:** Claude Code session 01LXPmm8VuMHBjo4Q6k7tRtq (delegated by hironow)

## Current State

v0.1.8 is published on PyPI (`firepact`) and crates.io (`firepact-core`) through
OIDC trusted publishing (ADR 0013), `main` is green, and every planned phase is
implemented. What the system does is in [`docs/README.md`](README.md); why it is
shaped that way is in [`adr/`](adr/). Today went into the supply chain and the
gates: a seven-day cooldown on all three ecosystems, one screened index, every
lockfile guarded, and every CI job running its `just` recipe so CI and local
cannot drift.

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

1. Work through Dependabot's uv pull requests as they arrive. They resolve
   now that the cooldown is relative, so the backlog it could not open should
   appear on its next run.
2. Decide whether bun should resolve through the Takumi Guard proxy as PyPI
   does. Two questions first: does `bun audit` work against it, and can CI
   reach it uncredentialed?
3. Still open from before: commit released bundles under `schemas/v*.json` and
   wire `firepact compat --history schemas` into CI, and grow `.semgrep/rules/`
   as patterns recur.

## Known Risks / Blockers

- `uv sync` skips rebuilding the in-tree PyO3 module when Rust changes without a
  version bump. Run `just build-ext` afterwards.
- The `importlib.import_module` call in `python/firepact/cli.py` trips the managed
  semgrep guardrail. Accepted false positive: a validated dotted path from
  build-time input, and that scanner ignores `# nosemgrep`.
- x86_64 macOS wheels cross-compile on the arm64 runner, the Intel image having
  been retired. Revisit if that matters past 2027.
- Dependabot's bun updater cannot read bun 1.4's `lockfileVersion 2`, so version
  updates for `tests/e2e/frontend` may fail. Until they do, `just
  frontend-audit` is its only vulnerability gate.

## Context the Next Actor Needs

- `main` is covered by the `protect` ruleset: pull requests only, squash merges
  only, linear history, no bypass, and all fifteen `ci.yaml` jobs required by
  name. Renaming one means editing the ruleset too; see
  [`docs/release.md`](release.md).
- `[tool.uv] exclude-newer` is a seven-day cooldown, not a date to maintain. uv
  records the span in `uv.lock` and recomputes it only on a new resolution, so
  `just deps-upgrade` is the only lever.
- The screened index is `[[tool.uv.index]]` in `pyproject.toml`, so `uv lock`
  records it with no environment variable. CI and Dependabot name the same URL.
- Nine `v*` tags exist with no GitHub Release against any. That is
  deliberate: the registries are the release surface.
- E2E needs bun and the emulator on `127.0.0.1:8080`, project `demo-firepact`,
  `singleProjectMode`, from `~/dotfiles/emulator`. CI runs it under
  `firebase emulators:exec`.
- `fixtures/` holds the canonical contract artifact, and the read-view projection
  is shared by emit and compat in `src/lib.rs`, so the gate cannot drift.
- Third-party actions need allowlisting under Settings, Actions, General.
  `extractions/setup-just` pulls in `extractions/setup-crate`, so both need
  entries.

## Relevant Files and Commands

- `.github/workflows/ci.yaml` — the CI gate; declares `permissions: contents: read`.
- [`docs/release.md`](release.md) — how a version reaches PyPI and crates.io.
- `pyproject.toml`, key `[tool.uv] exclude-newer` — the dependency cooldown.
- `src/lib.rs` — emitter, shared projection, PyO3 binding; `src/compat.rs` — gate.
- `just check` — the no-write gate: rust and python lint, types, markdown, links.
- `just test` / `just test-e2e` / `just build-ext` / `just deps-upgrade` /
  `just frontend-install` (the only writer of `bun.lock`).
- `just ci` — local CI parity; `just ci-all` adds the pydantic version matrix.
