# chat example

A complete input -> output pair for firepact:

- **`models.py`** - the Pydantic models (the input). `Message` is a
  `@firestore_realtime` root; `Profile`/`Reaction`/`MessageKind` are its
  transitive closure. Wire keys are camelCase (`by_alias=True` + `to_camel`),
  matching the backend's write serialization.
- **`generated.ts`** - the firepact output (the final result): read/write/update
  views, the read converter (doc-id injection), open string enums, and a typed
  path helper. Committed so the pair is visible at a glance.

## Regenerate

```sh
just example          # or:
firepact-gen --module examples.chat.models --output examples/chat/generated.ts
```

A test (`tests/integration/test_emit_chain.py::test_committed_example_output_is_current`)
keeps `generated.ts` from drifting out of sync with `models.py`.
