# compat example

The worked reference for the **compatibility gate**. The generation examples live
in [`../gen/`](../gen/); this one is about firepact's *other* job: stopping a
contract change that would break a deployed frontend.

## What's here

- **`models.py`** - one Firestore document, `Account`, at its **current**
  version.
- **`schemas/`** - the **released** contract bundles, in version order:
    - `account.v0.json` - the first release (`id`, `created_at`, `version`,
    `email`).
    - `account.v1.json` - adds `display_name`.

  Each is a real `firepact-gen --bundle-out` artifact, frozen at release time. A
  project commits one such file per release.

## How the gate works (FULL_TRANSITIVE)

`just example-compat` exports the **current** model's bundle and diffs it against
**every** committed past version:

```sh
firepact-gen --module examples.compat.models --bundle-out output/account.bundle.json
firepact compat --history examples/compat/schemas --new output/account.bundle.json
```

The current model is compatible with both v0 and v1, so the gate passes:

```text
[account.v0.json] SAFE     Account.display_name field added (read-optional)
compat: compatible with all 2 past version(s)
```

Adding an **optional** field (here `display_name`, v0 -> v1) is SAFE: an old
frontend built against v0 ignores it, and a new frontend tolerates its absence on
residual v0 documents. The gate is transitive -- the current contract must stay
readable by a frontend built against *any* past version, not just the latest.

### What it would reject

Try editing `models.py` and re-running `just example-compat`:

- removing `email`, or making `display_name` required, → **BREAKING** (a frontend
  built against an older version would now mis-read documents); the gate exits
  non-zero.
- adding another optional field → SAFE.

That is the whole point: the gate mechanically prevents a contract change that
would break a client, before the bundle is released.

## Releasing a new version

When a change is intentional and safe, freeze the new bundle as the next history
entry (`firepact-gen --bundle-out examples/compat/schemas/account.v2.json`) and
commit it; it then becomes part of the transitive history every future change is
checked against.
