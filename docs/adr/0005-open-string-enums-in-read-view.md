# 0005. Open string enums in the read view

**Date:** 2026-06-05
**Status:** Accepted

## Context

A backend adding an enum value breaks an old frontend's exhaustive handling
(forward break) under a strict enum. Under FULL_TRANSITIVE (ADR 0004), enum
evolution must be neutral in both directions, or enums become un-evolvable.

## Decision

Project string enums as an **open union** in the read view:
`"a" | "b" | (string & {})` (and the named form `Kind | (string & {})`). The
write view stays strict (`Kind`); the enum def is emitted once, view-agnostic.
Numeric enums stay strict (no clean open idiom). The compat gate normalizes any
read type containing `(string & {})` to `string`, so enum member add/remove (and
enum<->string) is classified SAFE.

## Enforcement inventory

### Entry points
- The emitter's read-view rendering of any field whose type is a string enum
  (named `$ref` or inline `Literal`).
- The compat gate's field signature, which must treat such fields as `string`.

### Persistent / carried data needed at each enforcement point
- The enum members in the bundle; the `(string & {})` marker that both the
  emitter writes and the gate keys off.

### Bypass candidates ("where can this go wrong?")
- A numeric enum: intentionally left strict (documented), so its member changes
  are NOT neutralized -- a numeric-enum change is correctly flagged by the gate.
- An inline `Literal` (not a `$ref`): handled, the open marker is applied inline.
- The gate computing a signature differently from the emitter: prevented by ADR
  0004's shared projection (`read_type_signature`).

### Tests proving coverage
- `tests/open_enum.rs`: read open / write strict / single def / int-enum strict /
  inline open.
- `tests/compat.rs`: `enum_value_add_is_safe`, `enum_value_remove_is_safe`.

## Consequences

### Positive
- Enum evolution is fully backward/forward compatible for string enums.

### Negative
- The read type is wider than the declared enum; exhaustiveness checks on reads
  must handle the open case.

### Neutral
- Numeric enums do not get this guarantee.
