# What firepact is — and what it is not

firepact is easy to mistake for something it is not. This page draws the boundary
of its guarantees so the green checkmark is read correctly.

## What it is

firepact is two things over the **wire shape of Firestore Native-mode documents
read in realtime via `onSnapshot`**:

1. A **type-contract generator** — Pydantic models become a single enriched JSON
   Schema 2020-12 bundle, and the emitter projects read / write / update TypeScript
   views from it (see [contract.md](contract.md), [architecture.md](architecture.md)).
2. A **static FULL_TRANSITIVE compatibility gate** — `firepact compat` diffs two
   bundles and fails CI on a breaking change to the read contract (see
   [compatibility.md](compatibility.md)).

The value sits in two places: the wire types are correct for the realtime SDK
(`Timestamp`, `Bytes`, `DocumentReference`, `GeoPoint`, `VectorValue`, open
enums), and the gate is computed from the same read-view projection the emitter
uses, so the generator and the gate cannot drift apart.

## What it is NOT (common misunderstandings)

### 1. It does not verify the data in Firestore — only the evolution of the contract

The gate proves that the **contract** evolved compatibly (old readers can read new
documents and new readers can read old documents). It proves **nothing** about the
documents actually sitting in Firestore. A green gate does not mean production
reads are safe.

Native mode is schema-less: anything can write any shape. Data written **outside
the Pydantic path** — a Go Cloud Function, a hand edit in the console, a legacy
mobile client that bypassed the contract — can violate the wire types while the
gate stays green, and the realtime read breaks at runtime.

In registry terms, firepact is closest to **Confluent Schema Registry's
compatibility check**: a *static contract gate*. It is **not** a *verified
contract* in the [Pact](https://pact.io) sense — there is no consumer-side
verification of real interactions. The "pact" in the name means the **contract**,
not Pact-the-tool's verification model.

### 2. FULL_TRANSITIVE does not mean "all history is safe"

The transitive guarantee holds **from the first committed bundle forward**.
Documents written *before* that baseline are outside the guarantee; individual
fields can be rescued with `FirestoreBackfilled` (see [compatibility.md](compatibility.md)).

This makes **retrofitting firepact onto an existing, long-lived Firestore the
sharpest edge.** "FULL_TRANSITIVE" reads like "every generation of document is
safe," but adoption only protects from the baseline bundle onward — it cannot
vouch for years of pre-existing data. Treat the first committed bundle as the line
the guarantee starts at, not the beginning of time.

### 3. It does not enforce writes at runtime

firepact generates **TypeScript compile-time types only**. It does **not** generate
Firestore Security Rules. Write safety therefore rests entirely on the discipline
that *every* writer goes through the generated `{Name}Write` types. The moment a
writer skips them — a non-TypeScript service, a script, a rules-bypassing path —
the contract is advisory, not enforced. The model implicitly assumes a **single,
TypeScript, contract-respecting writer**; Firestore does not guarantee that.

### 4. It is not a general-purpose tool

It fits exactly one shape: **Firestore Native mode + realtime `onSnapshot` +
Pydantic + TypeScript**. Outside that quad the strictness is overkill —
Datastore mode, or a one-shot `getDoc` mapped on the server, or any non-realtime
read does not need a FULL_TRANSITIVE wire-shape gate.

## When to use it

- A Pydantic backend (FastAPI, etc.) and a TS web/React Native frontend that
  **subscribes to Firestore in realtime**, where the document shape grows over time
  or a different team in a different repo can silently drift the wire shape. The CI
  gate becomes the referee for the contract.
- Right before a risky schema change to a collection that **already holds live
  history**, when you want a mechanical proof that existing-document readers survive.

## When not to use it

- When the **write surface is polyglot and outside your control** (heavy mobile
  direct-writes, many non-TypeScript functions). The contract drops to advice, and
  a green gate can coexist with broken production.
- A **greenfield schema that changes weekly**. Before 1.0 you *want* to break
  things, but every retype is BREAKING and fights the gate. Adopt after
  stabilization, not at the start.
- When the team **cannot keep the discipline of committing bundle history**. Without
  it the gate has nothing to diff against and degrades into ritual.

## Related tools

- **Confluent Schema Registry** (compatibility modes) — the closest analog;
  firepact is the same idea applied to Firestore wire shapes.
- **Pact** — a different model (consumer-driven contracts verified against real
  interactions). firepact does not do interaction verification.
