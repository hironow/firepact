# Handover

**Last updated:** 2026-06-05 (JST)
**Updated by:** claude (Phase 0 session)

## Current State

Phase 0 is functionally complete and **shippable**: the full chain works and is
proven by a real-emulator E2E.

- Rust core (`firepact-core`, bin `firepact`): `emit` projects the contract
  bundle into read/write TypeScript; `compat` is a stub (Phase 1). CLI takes
  subcommands and reads the bundle from a file or stdin.
- Emitter features landed: wire-type mapping, read/write projection, **open
  string enums** in the read view (pulled forward; the compat gate's premise),
  and a **minimal doc-id converter** for realtime roots (so `id: string` holds).
- Python extractor (`python/firepact`): imports `@firestore_realtime` roots,
  delegates schema generation to Pydantic, stamps `x-firestore-*`, injects root
  collection + doc-id. `by_alias=True` pinned by a guard test.
- E2E (`tests/e2e`): backend write -> generate -> `tsc --noEmit` -> `onSnapshot`
  read through the generated converter. Both checks pass.

All commits are Conventional Commits with structural/behavioral separated.
`just test` (rust + python unit/integration) and `just lint` are green; `just
test-e2e` passes against the running emulator.

## In Progress

Phase 0d done. **Checkpoint for requester review** (as requested: review once the
Phase 0 E2E passes). Next: Phase 0e (maturin/PyO3 packaging).

## Next Actions

1. Requester review of Phase 0.
2. Resolve the two open questions in `docs/intent.md` (OTel exclusion; name
   reservation timing).
3. Phase 0e: maturin/PyO3 (swap subprocess for native `emit`/`compat`,
   `from firepact import generate_typescript_defs`, console scripts).
4. Phase 1: `firepact compat` (HANDOFF S5.2 taxonomy as a test table; ADR 0004
   with the required Enforcement inventory).
5. Phase 3 then Phase 2.

## Known Risks / Blockers

- `python/firepact/cli.py` uses `importlib.import_module(<module-arg>)` -- the
  intended `--module` mechanism (same as the prior tool; developer build-time
  input, validated to a dotted path). The global semgrep guardrail flags it as a
  false positive; inline `# nosemgrep` is not honored by that managed scanner.
  Accepted and documented; the tested core API has no dynamic import.
- Python pinned to 3.13 for dependency wheels (google-cloud-firestore, etc.).

## Context the Next Actor Needs

- Emulator: `127.0.0.1:8080`, project `demo-firepact`, `singleProjectMode`
  (from `~/dotfiles/emulator`, assumed running).
- The fixture pair under `fixtures/` is the canonical contract artifact: schema
  layer (`message.bundle.json`, frozen Pydantic output) and emit layer
  (`message.generated.ts`). Golden tests compare both.
- The read-view projection logic will be shared with the compat gate; extract it
  to avoid drift (planned `contract.rs`).

## Relevant Files and Commands

- `src/lib.rs` - emitter (emit, projection, open enum, converter).
- `src/main.rs` - CLI (emit/compat, stdin).
- `python/firepact/firestore_schema.py` / `firestore_select.py` - extractor.
- `examples/chat/models.py` - canonical example models.
- `fixtures/` - golden contract artifacts.
- `just test` / `just lint` / `just test-e2e` - verify.
