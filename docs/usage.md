# Usage

The current command and API surface. See [contract.md](contract.md) for the
annotations and projection rules, and [compatibility.md](compatibility.md) for
the gate.

## 1. Annotate models

```python
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from firepact import (
    FirestoreBackfilled,
    FirestoreRef,
    FirestoreServerTimestamp,
    firestore_realtime,
)


class CamelModel(BaseModel):
    # by_alias=True + to_camel MUST match the backend's write serialization.
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


@firestore_realtime(collection="rooms/{roomId}/messages", id_field="id")
class Message(CamelModel):
    id: str
    author: Annotated[str, FirestoreRef("Profile")]
    body: Annotated[str, FirestoreBackfilled()]
    created_at: Annotated[datetime, FirestoreServerTimestamp()]
    kind: MessageKind  # a StrEnum, defined above
    ...
```

Only models decorated with `@firestore_realtime` are roots; their transitive
closure (nested models, enums) is included automatically. A full worked example
is in [`../examples/chat/`](../examples/chat/).

## 2. Generate TypeScript

CLI (imports the module, builds the bundle, emits TS):

```sh
firepact-gen --module pkg.models --output types.ts   # native entry point
pydantic2ts  --module pkg.models --output types.ts   # prior-tool-compatible alias
```

`--module` is resolved against the current working directory. `--output` is
optional (defaults to stdout). `--exclude` is accepted for prior-tool
compatibility (no-op).

Python API:

```python
from firepact import generate_typescript_defs
ts = generate_typescript_defs("pkg.models", output="types.ts")
```

Low-level (bundle then Rust core):

```sh
firepact emit pkg.bundle.json    # or: cat pkg.bundle.json | firepact emit -
```

## 3. Use the generated types

The emitter produces, per realtime root `Message`:

- `Message` - the **read** view (`onSnapshot` / `getDoc`).
- `MessageWrite` - the **write** view (`setDoc`, create payload).
- `MessageUpdate` = `Partial<MessageWrite>` - the **update** view (`updateDoc`).
- `messageConverter` - a read-oriented `FirestoreDataConverter<Message>` that
  injects the document id on read and strips it on write. Reads go through it;
  **writes use `MessageWrite` directly** (FirestoreDataConverter has a single app
  type, so the read/write asymmetry cannot both be expressed through it).
- `messagesPath(roomId)` - a typed path builder from the collection template.

```ts
import { messageConverter, messagesPath, type MessageWrite } from "./types";

const ref = doc(db, `${messagesPath(roomId)}/m1`).withConverter(messageConverter);
onSnapshot(ref, (snap) => {
  const m = snap.data();        // Message, with m.id populated
});

const payload: MessageWrite = { /* createdAt: serverTimestamp(), ... */ };
await setDoc(doc(db, `${messagesPath(roomId)}/m1`), payload);  // write view, no converter
```

## 4. Gate compatibility (CI)

```sh
firepact compat old.json new.json                 # pairwise
firepact compat --history schemas/ --new new.json # FULL_TRANSITIVE vs every past version
```

Exit code is non-zero on any breaking change. See [compatibility.md](compatibility.md).

## Tasks

`just` lists all tasks. Common ones: `just build`, `just test`, `just lint`,
`just test-e2e` (needs the Firestore emulator + bun), `just example` (regenerate
`examples/chat/generated.ts`).
