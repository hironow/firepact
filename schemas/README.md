# schemas/

Versioned history of the **contract bundle** for the `examples/gen/chat` models -
one committed file per published release. This is what the FULL_TRANSITIVE
compatibility gate diffs against; in a real project, point it at your own models.

## Convention

- One bundle per release: `message.v1.json`, `message.v2.json`, ...
- Generated with `firepact-gen --module <mod> --bundle-out schemas/<name>.vN.json`
  (deterministic, `sort_keys`ed).
- A release's bundle is committed **only after** `firepact compat` passes against
  the existing history.

## Gate it

```sh
just compat   # regenerate the current bundle and diff it against every file here
```

which runs:

```sh
firepact compat --history schemas --new output/message.bundle.json
```

Non-zero exit on any breaking change. See [../docs/compatibility.md](../docs/compatibility.md).
