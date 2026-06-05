# chat example

The worked reference for the real **layered** firepact setup: Firestore documents
and plain HTTP DTOs, generated into separate files with each shared enum defined
exactly once.

## Inputs (Pydantic)

- **`models.py`** - the Firestore document models. `Message` is a
  `@firestore_realtime` root; `Profile`/`Reaction`/`Attachment` are its transitive
  closure. Wire keys are camelCase (`by_alias=True` + `to_camel`), matching the
  backend's write serialization.
- **`dtos.py`** - plain HTTP request/response DTOs (`SendMessageRequest`,
  `SendMessageResponse`). Their `datetime` is an ISO **string** over HTTP, not a
  Firestore `Timestamp`. `MessageKind` is shared with `Message` and is defined
  here (the plain layer is the single source).

## Outputs (TypeScript)

- **`dtos.ts`** - generated with `firepact-gen --plain`: one plain interface per
  model, `datetime` -> `string`, strict enums. Defines `MessageKind`.
- **`generated.ts`** - the Firestore contract: read/write/update views, the read
  converter (doc-id injection), open string enums, a typed path helper. It
  **imports** `MessageKind` from `./dtos` (via `--shared-from`) instead of
  redefining it, so every type is defined exactly once across the two files.

## Regenerate

```sh
just example
# which runs:
firepact-gen --plain --module examples.chat.dtos --output examples/chat/dtos.ts
firepact-gen --module examples.chat.models --output examples/chat/generated.ts \
  --shared ./dtos --shared-from examples.chat.dtos
```

`--shared-from examples.chat.dtos` derives the shared names from the dtos module's
own output (the types it defines), so there is no hand-maintained list and the
imported names are guaranteed to exist in `dtos.ts`; firepact imports only the
ones the Firestore docs actually reference.

`tests/integration/test_emit_chain.py` keeps both outputs from drifting.
