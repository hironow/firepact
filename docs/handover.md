# Handover

**Last updated:** 2026-09-04 (JST)
**Updated by:** Claude Code session (delegated by hironow)

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

- [PR #38](https://github.com/hironow/firepact/pull/38) bumps
  `actions/setup-java` 5.7.0 to 6.0.0. All 15 checks are green and it is
  mergeable; it only needs a merge.
- Eight open code scanning alerts, all produced by the first CodeQL run.

## Next Actions

1. Merge PR #38.
2. Clear the eight CodeQL alerts. Each is `actions/missing-workflow-permissions`
   against `.github/workflows/ci.yaml`, one per job, because that workflow
   declares no `permissions:`. Add a top-level `permissions: contents: read` the
   way `release.yaml` already does, rather than dismissing the alerts.
3. Unblock the uv ecosystem by advancing `[tool.uv] exclude-newer` in
   `pyproject.toml` past the versions Dependabot is trying to reach, then
   re-locking. The failure and the required index are under Known Risks.
4. Still open from before: commit released bundles under `schemas/v*.json` and
   wire `firepact compat --history schemas` into CI, and grow `.semgrep/rules/`
   as patterns recur.

## Known Risks / Blockers

- **Every Dependabot uv update currently fails.** `[tool.uv] exclude-newer` is
  pinned at `2026-08-14T00:00:00Z`, so `uv lock --upgrade-package` cannot resolve
  ruff 0.16.5, mypy 2.3.1, or google-cloud-firestore 2.29.0, each published after
  that cutoff. The date has to be moved by hand; this does not self-heal.
- **Re-lock only under the Takumi Guard index.** CI injects
  `UV_INDEX_URL=https://pypi.flatt.tech/simple/`, so a lockfile resolved against
  pythonhosted URLs fails `uv sync --locked`. Export that variable before
  `uv lock`.
- `uv sync` skips rebuilding the in-tree PyO3 module when Rust changes without a
  version bump. Run `just build-ext` after touching Rust.
- The `importlib.import_module` call in `python/firepact/cli.py` trips the managed
  semgrep guardrail. Accepted false positive: a validated dotted path from
  build-time developer input, and that scanner ignores inline `# nosemgrep`.
- Third-party actions must be allowlisted under Settings, Actions, General.
  `extractions/setup-just` pulls in `extractions/setup-crate`, so both need an
  entry before CI setup will run.
- x86_64 macOS wheels are cross-compiled on the arm64 runner, the Intel image
  having been retired. Revisit if that coverage matters past 2027.

## Context the Next Actor Needs

- `main` carries no branch ruleset, but changes still go through a pull request.
- E2E is local-only: it needs bun and the Firestore emulator on `127.0.0.1:8080`,
  project `demo-firepact`, `singleProjectMode`, from `~/dotfiles/emulator`. The
  CI e2e job runs it under `firebase emulators:exec`.
- `fixtures/` holds the canonical contract artifact, and the read-view projection
  is shared by emit and compat in `src/lib.rs`, so the gate cannot drift.
- To release: bump `pyproject.toml` and `Cargo.toml` together, tag `vX.Y.Z`, push,
  then approve the `release` environment. The runbook is the git-ignored
  `private/PUBLISH_HOWTO.md`.

## Relevant Files and Commands

- `.github/workflows/ci.yaml` — what the CodeQL alerts point at.
- `pyproject.toml`, key `[tool.uv] exclude-newer` — the uv resolution cutoff.
- `src/lib.rs` — emitter, shared projection, PyO3 binding; `src/compat.rs` — gate.
- `just check` — the no-write gate: rust and python lint, types, markdown, links.
- `just test` / `just test-e2e` / `just build-ext` / `just example-gen`.
- `just ci` — local CI parity; `just ci-all` adds the pydantic version matrix.
