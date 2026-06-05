# 0011. Cross-file shared-type imports (`--shared`)

**Date:** 2026-06-05
**Status:** Accepted

## Context

ADR 0010 added plain mode so a project can split its generated TypeScript into a
Firestore document file and a plain DTO file. But a context-independent type used
by both layers (e.g. a `StrEnum` referenced by a Firestore document AND an HTTP
DTO) was then **defined in both files** -- two structurally identical definitions.
ADR 0010 deferred deduplicating them, noting it would need cross-file imports.

## Decision

Add `emit_shared(bundle, shared_path, shared_names)` (CLI: `firepact-gen --shared
<module> --shared-names A,B`): the named `$defs` are **imported** from
`shared_path` (a TS module specifier resolved relative to the output file)
instead of defined, e.g. `import type { LanguageEnum } from "./types";`. Only
names actually referenced by the output are imported; unreferenced ones are
ignored.

The shared names are **explicit** (not auto-detected): firepact does not read the
target module, so it cannot verify the names exist there. The caller lists the
shared types and generates the source-of-truth file first (in the same
`server-gen` recipe); a wrong name surfaces at the consumer's `tsc`, which is the
explicit contract. Dual-context types (a model that is Timestamp-bearing when
embedded in a Firestore document but a plain DTO over HTTP) are simply NOT listed,
so each file keeps its own correct definition.

## Consequences

### Positive

- Every type is defined exactly once across the generated files; the Firestore
  file imports shared enums from the plain DTO file.

### Negative

- The shared-name list is maintained by hand (in the `server-gen` recipe); a typo
  is caught by `tsc`, not by firepact.

### Neutral

- Resolution is purely textual: firepact emits the module specifier verbatim; it
  is the caller's responsibility that `shared_path` resolves from the output file.
