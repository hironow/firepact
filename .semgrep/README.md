# firepact Semgrep rules

Project-specific static-analysis rules. Intentionally **light at project start**;
ruleset density grows toward mid-lifecycle once patterns stabilize (per the
project philosophy: write a rule the *second* time a review catches the same
thing).

## Layout

```
.semgrep/
  rules/{category}/{rule-id}.yaml   # one rule per file; filename == rule id
  tests/{category}/{rule-id}.<ext>  # at least one matching + one non-matching case
  README.md
```

- Rule id format: `firepact-{category}-{short-name}`.
- Use `.yaml` (never `.yml`).
- Every rule MUST ship a test file.

## Run

```sh
just semgrep
```

`just semgrep` runs the registry language packs `p/python`, `p/rust`, and
`p/typescript` (so there is real coverage even before any project rule exists),
plus `--config .semgrep/rules/` when this directory has rules. Findings fail
(`--error`); telemetry is off (`--metrics off`). It is wired into CI. Suppress a
verified false positive with an inline `// nosemgrep: <rule-id>` comment and a
reason (see `src/main.rs`).

## When to add a rule

- The same review comment has been made twice or more.
- An ADR decision needs mechanical enforcement.
- A production incident's root cause is expressible as a code pattern.

Do **not** add rules for things mypy or ruff already catch.

## Candidate rules (not yet codified)

- Forbid `datetime`/`Timestamp` fields typed as `string` in generated TS
  (`x-firestore-type` is authoritative -- docs/history/design.md S5.1 / ADR 0002).
- Forbid reintroducing a Node dependency in the Rust core (ADR 0003).
