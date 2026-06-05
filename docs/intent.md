# Intent

**Last updated:** 2026-06-05
**Requester:** hironow
**Work unit:** firepact implementation (Phase 0 -> 1 -> 3 -> 2)

## Goal

Build `firepact`: keep a Python (Pydantic/FastAPI) backend and a TypeScript
frontend in agreement about the **wire shape of Firestore Native-mode documents
read in realtime via `onSnapshot`**, and mechanically guard the
backward/forward compatibility of that contract over time. It is a type contract
for a schema-less DB plus a compatibility gate -- not merely a type converter.

## Success Criteria

- Golden: example models -> extractor bundle == `fixtures/message.bundle.json`,
  and emit == `fixtures/message.generated.ts`.
- E2E (real Firestore emulator, no mocks): a backend-written doc is read via
  `onSnapshot` by a frontend compiled against the generated types, with no type
  errors and the read contract intact at runtime.
- Compatibility gate covers every row of the HANDOFF S5.2 taxonomy with a
  minimal case each; FULL_TRANSITIVE.
- Deterministic output (so the gate never false-positives on ordering).

## Scope

### In scope
- All phases in order: 0 (extractor + emit + E2E, shippable), 1 (compat gate),
  3 (CI follow: pydantic matrix + 2-layer insta snapshots + Renovate),
  2 (converter/open-enum/tuple/discriminated-union/update view, by demand).

### Out of scope (Non-goals)
- A general multi-dialect JSON Schema -> TS compiler (DESIGN S2.2; what killed
  the predecessor).
- Reimplementing Pydantic introspection in Rust (schema generation is delegated
  to Pydantic).

## Constraints (confirmed with requester)
- E2E uses the `~/dotfiles/emulator` Firestore emulator, assumed running.
- Python<->Rust integration: subprocess first, maturin/PyO3 later.
- Backend write convention: `by_alias=True` + `alias_generator=to_camel`
  (camelCase). The extractor MUST match it exactly (trap #1).

## Open Questions
- [ ] OpenTelemetry: proposed exclusion for a build-time codegen CLI (not a
      service). Needs requester confirmation (deviation from the global standard).
- [ ] Name reservation (PyPI `firepact`, crates.io `firepact-core`, GitHub):
      outward-facing, needs requester credentials; prepare metadata now, publish
      at the requester's hand near release.
