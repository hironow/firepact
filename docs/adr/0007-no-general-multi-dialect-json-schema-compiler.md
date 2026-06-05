# 0007. No general multi-dialect JSON Schema compiler

**Date:** 2026-06-05
**Status:** Accepted

## Context

Pydantic v2 emits JSON Schema Draft 2020-12 only. Generalizing firepact into a
multi-dialect (Draft 7 / 2019-09 / 4 / 6) JSON Schema -> TypeScript compiler, and
supporting advanced keywords (`$dynamicRef`, `$recursiveRef`, vocabularies,
`unevaluatedItems`), has poor ROI for this use case. The pull toward that
generality is what sent the predecessor to the WIP graveyard (DESIGN S2.2).

## Decision

Scope the input strictly to 2020-12 (Pydantic's default) plus the `x-firestore-*`
extension. Do not implement other dialects or advanced keywords Pydantic does not
produce. Firestore is the only target; its wire types and the read/write/update
projection are the value, not schema-language generality.

## Consequences

### Positive
- A small, finishable, maintainable tool focused on the real problem.

### Negative
- Not reusable as a general JSON Schema -> TS converter.

### Neutral
- If a future Pydantic emits a new 2020-12 construct, handle that specific
  construct -- not a new dialect.
