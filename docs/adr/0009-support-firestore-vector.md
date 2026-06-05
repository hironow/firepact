# 0009. Support the Firestore Vector type (`VectorValue`)

**Date:** 2026-06-05
**Status:** Accepted

## Context

Firestore added a Vector field type (`VectorValue`, for vector search) after
DESIGN.md was written, so it is absent from the §5.1 wire-type table. The client
SDK exposes it (`firebase/firestore` exports `VectorValue` and `vector()`); the
admin SDK writes it (`google.cloud.firestore_v1.vector.Vector`). It is a real
Firestore value type, so the contract should cover it.

This also validated the extension model: adding a Firestore type is meant to be a
small, local change through the `x-firestore-*` vocabulary, not a redesign.

## Decision

Add `vector` to the `x-firestore-type` vocabulary. A field annotated
`Annotated[list[float], FirestoreVector()]` is stamped `x-firestore-type:
"vector"`, and the emitter renders it as `VectorValue` (imported from
`firebase/firestore`) in both views. The change was exactly three local edits:
the `FirestoreVector` annotation, one `render_firestore` branch, and a manifest
row in `tests/firestore_field_types.rs` (which then forced golden + E2E
coverage). Verified end to end on the emulator (`Vector([...])` written by the
admin SDK reads back as `VectorValue`).

## Consequences

### Positive
- All Firestore field value types are now supported and E2E-verified; the
  type-coverage manifest (forget-guard) has no known gaps.
- Demonstrates the architecture's extensibility: a new wire type = annotation +
  one emit branch + one manifest row.

### Negative
- Vector search *queries*/indexes are out of scope (firepact maps the value
  type, not query semantics) — consistent with it being a wire-contract tool.

### Neutral
- The Python value is a plain `list[float]`; the backend converts to
  `Vector(...)` on write (converter responsibility, as with references).
