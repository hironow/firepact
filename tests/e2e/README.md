# E2E tests

Verifies the whole contract end to end with **no mocks**: a Python backend
writes a Firestore document through the real emulator, and a TypeScript frontend
compiles against the firepact-generated types and reads it back via `onSnapshot`.

## Requirements

- **Firestore emulator** reachable on `127.0.0.1:8080` (project `demo-firepact`,
  `singleProjectMode`). The repo assumes the `~/dotfiles/emulator` stack is
  already running; start it there if needed.
- **bun** (runs the TypeScript reader and `tsc`).
- The `e2e` dependency group (`uv sync --group e2e`) for `google-cloud-firestore`.
- The `firepact` binary built (`just build`).

The suite auto-skips when the emulator or bun is unavailable.

## Run

```sh
just test-e2e
```

## What it checks

1. `test_generated_types_compile` — `tsc --noEmit` over `consumer.ts` + the
   generated read/write views + converter (static contract).
2. `test_onsnapshot_reads_written_doc` — the backend writes `rooms/r1/messages/m1`
   with camelCase (`by_alias=True`) keys, `serverTimestamp()` for `createdAt`, and
   a `DocumentReference` for `author`; the frontend reads it through the generated
   `messageConverter` and asserts the read view holds at runtime (`id` injected,
   `createdAt instanceof Timestamp`, `author instanceof DocumentReference`).

## Files

- `frontend/` — the consumer app (`package.json`, `tsconfig.json`, `consumer.ts`,
  `reader.ts`). `generated.ts` is produced by the test run and git-ignored.
- `test_onsnapshot.py` — orchestration (write -> generate -> tsc -> read).
