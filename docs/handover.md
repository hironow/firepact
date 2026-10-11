# Handover

**Last updated:** 2026-10-11 (JST)
**Updated by:** Codex

## Current State

The dependency rollup PR #77 is merged. Python packages resolve from the
public PyPI registry. No CI, project or Dependabot setting selects Takumi Guard.
The registry migration preserves all 35 package versions and their artifact
hashes, plus the seven-day cooldown. Existing Rust, Python, generated frontend,
FULL_TRANSITIVE compatibility, emulator E2E and CodeQL gates remain in place.
Every CI job skips drafts and resumes on `ready_for_review`.

## In Progress

[PR #78](https://github.com/hironow/firepact/pull/78) removes the mirror from
configuration and lock URLs. Initial CI and CodeQL checks all passed (20 total).
An isolated Python 3.13 `just lock-check` installed from PyPI successfully;
`just check-workflows` passed its two regressions. The current maintenance
commit also aligns the handover and installer comments with the public registry.

## Next Actions

Verify all checks on the final PR head, squash merge, remove the obsolete
Flatt action allowlist pattern, then verify main CI.

## Context the Next Actor Needs

- Preserve the required CI job names and locked Cargo/uv and frozen Bun gates.
- The dated Takumi Guard npm research is retained as historical evidence.
- Local emulator E2E needs Java and firebase-tools; CI checks the real path.
- Same-version Rust edits need `just build-ext` to rebuild the Python extension.
- Release tags use the protected release environment and OIDC publishing.
  No release tag or published package is part of this maintenance work.

## Relevant Files and Commands

- `.github/workflows/ci.yaml` — required gates and draft policy.
- `tests/unit/test_workflow_policy.py` — draft/ready regression checks.
- `just lock-check` / `just check-workflows` — frozen install and workflow policy.
- `just test` — Rust and Python tests, including native parity.
- `just ci-all` — CI parity including emulator E2E and the Pydantic matrix.
