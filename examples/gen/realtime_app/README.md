# realtime_app example

The **production-style** reference: how a real app (with firepact kept out of its
model source) wires firepact in. Compare with [`../chat/`](../chat/), which shows
the decorator-on-model style.

## Why firepact exists: `datetime` is not one TypeScript type

A Pydantic `datetime` serializes **differently per channel**, and the correct
TypeScript type differs with it:

| Where the value lives | Stored/sent as | firepact TS type |
|---|---|---|
| Firestore document field (read via `onSnapshot`/`getDoc`) | a native Firestore **Timestamp** | `Timestamp` |
| Firestore document field (write via `setDoc`) | Timestamp (or a JS `Date`) | `Timestamp \| Date` |
| Firestore **server** timestamp (`serverTimestamp()`) | written as a `FieldValue`, read back as a Timestamp (null until the server fills it) | read `Timestamp \| null`, write `FieldValue` |
| Plain **HTTP** DTO (JSON over the wire) | an ISO 8601 **string** | `string` |

firepact emits the right type for each channel, so a Firestore read gives you a
real `Timestamp` (call `data.created_at.toDate()`) while an HTTP payload gives you
a `string` (parse with `new Date(...)`). The two never get confused, because they
are different generated types.

### Dual-context: `ChatMessage` is two distinct types, on purpose

`ChatMessage` (one Pydantic class in `dtos.py`) is embedded in the Firestore
`Chat` document **and** returned inside the HTTP `GetChatResponse`. firepact emits
it **distinctly** in each file -- this is the whole point, not an accident:

```ts
// firestore.ts  -- the Firestore document shape (read via onSnapshot)
export interface ChatMessage {
  created_at?: Timestamp;            // a Firestore Timestamp -> data.created_at.toDate()
  id?: string;
  role?: MessageRole | (string & {});
  text?: string;
}

// dtos.ts  -- the HTTP payload shape (JSON from fetch())
export interface ChatMessage {
  created_at: string;                // an ISO 8601 string -> new Date(created_at)
  id: string;
  role: MessageRole;
  text: string;
}
```

Same field name, **different type**: `Timestamp` inside Firestore, `string` over
HTTP. One TS type cannot be both, so firepact does **not** share dual-context
objects -- `ChatMessage` is defined in *both* files, each correct for its channel.
(The Firestore read view is also all-optional, since a nested type is never a
guaranteed root, and `role` is an open enum on read; the HTTP shape is strict.)
Only context-independent types -- the enums -- are imported across the files.

## The production wiring

- **`repo.py`** - the Firestore document models (`User`, `Chat`). Plain
  `BaseModel`, snake_case wire keys, and **no firepact import** -- firepact is a
  dev/gen-only dependency, kept out of the production import path.
- **`dtos.py`** - plain HTTP DTOs + the shared enums (`MessageRole`,
  `ChatStatus`). The single source for the enums.
- **`_fp_roots.py`** - generation-only. Registers the existing `repo` models with
  `firestore_realtime(...)(Cls)` (the decorator applied as a function), so
  `repo.py` is never modified. `id_field=None` keeps `id` a normal stored field;
  `guaranteed=[...]` marks the fields present since each collection's first
  version as read-required.

## Outputs

- **`dtos.ts`** (`--plain`): one interface per DTO, every `datetime` -> `string`,
  strict enums. Defines `ChatMessage` (string), `ChatStatus`, `MessageRole`.
- **`firestore.ts`**: all roots in one file (`User`; `Chat` under the
  `users/{userId}/chats` subcollection, so `chatsPath(userId)` is typed). Every
  `datetime` -> `Timestamp` (read) / `Timestamp | Date` (write); read/write/update
  views; read converters. Imports the enums from `./dtos` (via `--shared-from`),
  but keeps its **own** `Timestamp`-typed `ChatMessage`.

### `guaranteed` in action

In `firestore.ts`'s read `User`: `handle: string` is read-**required** (present
since v0), but `plan?: string` is read-**optional** even though it is required in
Pydantic -- it was added in v1, so a residual v0 document genuinely lacks it
(FULL_TRANSITIVE safe). `created_at`/`updated_at` are likewise read-required.

## Regenerate

```sh
just example   # regenerates both examples; for this one:
firepact-gen --plain --module examples.gen.realtime_app.dtos \
  --output examples/gen/realtime_app/dtos.ts
firepact-gen --module examples.gen.realtime_app._fp_roots \
  --output examples/gen/realtime_app/firestore.ts \
  --shared ./dtos --shared-from examples.gen.realtime_app.dtos
```

`tests/integration/test_realtime_example.py` keeps the outputs from drifting.
