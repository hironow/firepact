# Historical seed documents

These are the **original design and handoff documents** written at project
inception (largely in Japanese, WIP-era). They are kept **verbatim** as a
historical record and are intentionally excluded from the markdownlint pass and
from the "current state only" rule that governs the rest of `docs/`.

They are **not** the live documentation. For the current system, read:

- the live docs in [`../`](../) — `architecture.md`, `contract.md`,
  `compatibility.md`, `usage.md`, `scope.md` (the "What");
- the decision records in [`../adr/`](../adr/) — the "Why".

| File | What it was |
|---|---|
| [`design.md`](design.md) | The original `DESIGN.md` seed: full design narrative, the `x-firestore-*` vocabulary, the read/write/update projection rules, the five "traps". Most of it now lives in the ADRs and the live docs. |
| [`handoff.md`](handoff.md) | The original `HANDOFF.md`: the implementation handoff with the S5.2 compatibility taxonomy and phase plan. |

> Some immutable ADRs (e.g. `0008`, `0009`) reference `DESIGN.md` in prose. Those
> references are left as written — an ADR records what was true when it was
> accepted, so the historical name is correct in that context.
