# 0001. Delegate schema generation to Pydantic

**Date:** 2026-06-05
**Status:** Accepted

## Context

Pydantic models are dynamic Python runtime objects (generics, `computed_field`,
custom `__get_pydantic_core_schema__`, validators). Statically reconstructing
their shape in Rust would amount to re-implementing Pydantic, and would lag every
Pydantic release -- the opposite of "track the latest".

## Decision

Generate the JSON Schema with Pydantic itself (`models_json_schema`), producing a
single bundle with a shared `$defs` (the transitive closure is expanded for
free). The Rust core never introspects Python; it only consumes the enriched
bundle. The thin Python `extractor` is the only Pydantic-coupled code, so version
follow-up is confined to it plus any new 2020-12 output shapes Pydantic emits.

## Consequences

### Positive
- Pydantic compatibility is nearly free; new features flow through automatically.
- The Rust core stays Python-free and is just a deterministic bundle->TS function.

### Negative
- Importing the target module drags in its heavy dependencies (torch, etc.); CI
  must isolate generation.

### Neutral
- The contract artifact is whatever Pydantic emits (plus `x-firestore-*`), so the
  schema-layer golden is pinned per Pydantic version (see the CI drift matrix).
