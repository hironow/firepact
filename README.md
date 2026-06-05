# firepact

[![PyPI](https://img.shields.io/pypi/v/firepact)](https://pypi.org/project/firepact/)
[![crates.io](https://img.shields.io/crates/v/firepact-core)](https://crates.io/crates/firepact-core)
[![CI](https://github.com/hironow/firepact/actions/workflows/ci.yaml/badge.svg)](https://github.com/hironow/firepact/actions/workflows/ci.yaml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Keep your **Pydantic backend** and your **TypeScript frontend** agreeing on the
wire shape of **Firestore Native-mode documents read in realtime via
`onSnapshot`** — and fail CI on a schema change that would break a frontend still
reading the old shape (`FULL_TRANSITIVE`).

firepact is not just a type converter. It generates the TypeScript types your
frontend imports *and* runs a compatibility gate over the contract as it evolves.
Before you rely on the green check, read
[**what firepact is — and is not**](docs/scope.md): it gates the *evolution of the
contract*, not the data already sitting in Firestore.

## Install

```sh
pip install firepact          # Python CLI (firepact-gen / firepact-compat) + native engine
cargo install firepact-core   # standalone Rust binary `firepact` (no Python/Node)
```

## Quick start

**1. Mark the models you read in realtime.** The decorator records the collection
path and which fields are guaranteed on every document; the backend writes with a
camelCase alias generator (firepact matches it).

```python
from datetime import datetime
from typing import Annotated

from firepact import firestore_realtime, FirestoreServerTimestamp
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):                       # camelCase wire keys
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


@firestore_realtime(collection="rooms/{roomId}/messages", guaranteed=["body"])
class Message(CamelModel):
    id: str                                        # document id
    body: str
    created_at: Annotated[datetime, FirestoreServerTimestamp()]
    tags: list[str] = []
```

**2. Generate the TypeScript your frontend imports.**

```sh
firepact-gen --module app.models --output src/firestore.ts
```

```ts
// @firestore-collection rooms/{roomId}/messages
export interface Message {        // read view, for onSnapshot()
  body: string;                   // guaranteed -> required even on old docs
  createdAt?: Timestamp | null;   // server timestamp: null until it resolves
  id: string;                     // the converter injects snapshot.id
  tags?: string[];                // not guaranteed -> optional (safe default)
}

export interface MessageWrite {   // write view, for setDoc(): id is excluded
  body: string;
  createdAt: FieldValue;          // serverTimestamp()
  tags: string[];
}
```

The full worked example (refs, open enums, discriminated unions, vectors,
GeoPoints, bytes) is in [`examples/gen/chat/`](examples/gen/chat/).

**3. Gate compatibility in CI.** Export the contract bundle per release and diff
each change against the committed history; a breaking change fails CI.

```sh
firepact-gen --module app.models --bundle-out schemas/v2.json
firepact-compat --history schemas --new schemas/v2.json
```

See [usage](docs/usage.md) for the read/write/update views and the converter, and
[the compatibility gate](docs/compatibility.md) for what counts as breaking.

## Supported versions

Verified in CI (see [`.github/workflows/ci.yaml`](.github/workflows/ci.yaml)).

| Component | Supported | Notes |
|---|---|---|
| Python | 3.11 – 3.14 | one abi3 wheel covers 3.11+ |
| Pydantic | 2.9 – 2.13 | drift canary; the exact schema golden is pinned to the locked version |
| JSON Schema | Draft 2020-12 | Pydantic's default dialect |
| TypeScript (output) | 5.x / 6.x / 7.x | type-checks under `verbatimModuleSyntax` + `isolatedModules` |
| firebase JS SDK | v11+ | `Timestamp`, `GeoPoint`, `DocumentReference`, `Bytes`, `VectorValue`, `FieldValue`, `UpdateData`, `FirestoreDataConverter` |
| Rust | 1.75+ | MSRV (`Cargo.toml`) |

Dependency bumps within these ranges are tracked by Dependabot.

## Documentation

- [**scope**](docs/scope.md) — what firepact is and is **not** (read this first)
- [usage](docs/usage.md) — annotating models, the read/write/update views, the gate
- [contract & projection](docs/contract.md) — the `x-firestore-*` vocabulary
- [compatibility](docs/compatibility.md) — the `FULL_TRANSITIVE` gate and its taxonomy
- [architecture](docs/architecture.md) — the two components and the single bundle
- [`docs/adr/`](docs/adr/) — the decisions (the "Why")

## How it works

- **`firepact-core`** (Rust crate, binary `firepact`): pure, Python/Node-free.
  `firepact emit` projects one enriched JSON Schema bundle into read/write/update
  TypeScript; `firepact compat` is the gate.
- **`firepact`** (Python package): imports your Pydantic models, delegates schema
  generation to Pydantic, stamps the `x-firestore-*` vocabulary, and emits via the
  native core. Console scripts: `firepact-gen`, `firepact-compat`, and
  `pydantic2ts` (a drop-in alias for the prior tool).

## Contributing

```sh
just build           # build the Rust core + `firepact` binary
just test            # all tests (rust + python)
just lint            # rust + python + markdown checks
just example-gen     # regenerate the generation examples (examples/gen/)
just example-compat  # gate the compat example against its committed history
```

## Prior art & license

The Firestore-specialised, from-scratch successor to
[pydantic-to-typescript](https://github.com/hironow/pydantic-to-typescript)
(which targeted FastAPI request/response types and depended on Node). MIT licensed
([LICENSE](LICENSE)).
