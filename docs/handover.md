# Handover

**Last updated:** 2026-10-11 (JST)
**Updated by:** Codex

## Current State

v0.1.8 is published on PyPI and crates.io through OIDC trusted publishing
(ADR 0013). The dependency rollup contains PyO3 0.29.3, mypy 2.4.0 and its
required runtime dependencies, google-cloud-firestore 2.34.0, Firebase 12.19.0,
Node types 26.6.4, and setup-takumi-guard-pypi 1.3.0. Ruff 0.16.10 is already
on main through PR #74.

Every CI job skips draft pull requests and resumes on `ready_for_review`.
`just check-workflows` enforces this in the local gate and Python CI jobs.
The emulator CLI is installed through bun in CI.

## In Progress

Branch `chore/dependency-rollup-20261011` supersedes PRs #71, #72, #73, #75,
and #76. Local `just check`, `just test`, `just lock-check`, frontend audit,
`just frontend-typecheck`, `just example-compat`, `just semgrep`,
and the workflow regression checks pass. Final CI and CodeQL status must be
checked on the rollup head before squash merging; close the original PRs only
after that merge.

## Next Actions

1. Verify all rollup CI checks, including all four CodeQL language analyses.
2. Squash merge the validated head and close the five superseded PRs.

## Known Risks / Blockers

- Previous Dependabot heads had a neutral CodeQL result reporting missing
  analysis configurations. A fresh rollup run must produce successful results.
- Local Firestore E2E requires Java and firebase-tools, which are absent in this
  checkout's environment. The CI emulator job covers the real E2E path.
- `uv sync` can skip rebuilding same-version Rust source changes. Use
  `just build-ext` when editing the native extension.

## Context the Next Actor Needs

- The `protect` ruleset requires PRs, squash merges, linear history, and fifteen
  CI jobs. Preserve their names; see [`release.md`](release.md).
- Keep cooldowns, screened PyPI index, frozen bun installs, and locked uv/Cargo
  installs. Do not blanket-regenerate locks when diagnosing a red update.
- CodeQL default setup covers actions, Python, JavaScript/TypeScript, and Rust.
- Release tags require the protected `release` environment; registries are the
  release surface, not GitHub Releases.

## Relevant Files and Commands

- `.github/workflows/ci.yaml` — required gates and draft policy.
- `tests/unit/test_workflow_policy.py` — draft/ready regression checks.
- `just check` / `just test` — local lint, types, format, links, and fast tests.
- `just frontend-typecheck` / `just example-compat` — generated consumer types
  and FULL_TRANSITIVE compatibility.
- `just ci-all` — full CI parity, including real emulator and Pydantic matrix.
