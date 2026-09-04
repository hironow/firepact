# Should bun resolve through the Takumi Guard proxy?

**Date:** 2026-09-04
**Status:** snapshot; superseded by newer research

## Question

PyPI installs go through the Takumi Guard proxy, which blocks known-malicious
packages before they execute. bun does not: `tests/e2e/frontend/bunfig.toml`
pins the public registry. Should bun go through the proxy too?

Four things had to be true for that to be worth considering. The proxy has to
serve the advisories endpoint `bun audit` uses; CI has to reach it without
credentials; the seven-day `minimumReleaseAge` has to keep working; and the
lockfile must not become unusable off the proxy.

## Method

Read-only. Every measurement ran in a temporary directory copied from
`tests/e2e/frontend`, never in the repository, and nothing here changed any
configuration. Registry endpoints were probed with `curl`, resolution behaviour
with `bun install` against throwaway `bunfig.toml` files, and the tooling side
by reading action definitions and dependabot-core sources.

## What was measured

### The advisories endpoint works, and today's failure was weather

`bun audit --audit-level=high` through the proxy exits 0:
`No vulnerabilities found (checked 107 packages)` in 322ms. Against the public
registry, the same tree gives byte-identical output in 288ms. The proxy is not
serving a thinner advisory set for these packages.

Earlier the same day the proxy returned 502 and the public registry returned 503
in CI, three attempts apart. Re-probed at 13:49 UTC, three times each:

| Host | Result |
|---|---|
| `registry.npmjs.org` | 200, 200, 200 |
| `npm.flatt.tech` | 200, 200, 200 |

Both hosts had a transient outage on 2026-09-04. Neither lacks support.

### It is reachable without credentials

An unauthenticated packument fetch returns 200 from the proxy. The developer
machine that surfaced this question has no proxy-scoped credential in its
`~/.npmrc` at all, so its existing proxy traffic is already anonymous. This
matches the PyPI side, where `setup-takumi-guard-pypi` runs with no bot-id.

`flatt-security/setup-takumi-guard-npm` exists and has the same shape as the
PyPI action: anonymous when no bot-id is given, no OIDC token requested. It is
not on this repository's actions allowlist and would need an entry and a
full-SHA pin before use.

### But that action cannot reach bun here

The action configures the registry by writing `registry=` into `.npmrc`. Its own
description covers npm, pnpm and yarn; bun is not named. Measured directly:

| `bunfig.toml` | `.npmrc` | `bun install` |
|---|---|---|
| public registry | unreachable host | succeeds |
| absent | unreachable host | fails to resolve |

`bunfig.toml` wins. While it declares a registry, anything written to `.npmrc`
is inert, so adopting the action would change nothing. Routing bun through the
proxy means editing `bunfig.toml` itself, which gives up the property that a
developer's `~/.npmrc` cannot move the project's registry.

### The cooldown survives, and so does the lockfile

The packument `time` field comes back through the proxy with the same 268
entries and the same `latest` tag as the public registry, which is what
`minimumReleaseAge` reads.

Resolving the same `package.json` from scratch through each registry, with the
seven-day cooldown set both times:

| | Packages | Explicit URLs | Version differences |
|---|---|---|---|
| Public registry | 107 | 0 | baseline |
| Proxy | 107 | 0 | **0** |

Two things follow. The cooldown behaves identically through the proxy. And a
proxy-resolved lockfile carries no proxy URLs: bun omits the URL for whichever
registry is configured as the default, so the lock stays installable anywhere.
Proxying would not strand contributors, Dependabot, or a machine without proxy
access.

### Dependabot could be proxied on its own

dependabot-core's bun updater looks for a registry in the Dependabot config
first, then `.npmrc`, `.yarnrc` and `.yarnrc.yml`. It reads credentials of type
`npm_registry` and skips any without `replaces-base`. GitHub's private-registry
guidance says bun follows npm's configuration and that `.npmrc` is not required.

It never reads `bunfig.toml`. The registry pin is therefore already invisible to
Dependabot, which resolves wherever its own configuration points.

### earcon is unaffected either way

Its release workflow passes `--registry https://registry.npmjs.org` explicitly
on every `npm publish` and `npm view`, including the provenance check, so a
`bunfig.toml` registry change cannot reach publishing or attestation
verification. Its bunfig governs resolution and installation only.

## Conclusion

Proxying bun is technically unblocked. The proxy serves advisories, answers
anonymously, preserves the cooldown, resolves to identical versions, and leaves
no trace in the lockfile. Nothing in the earlier objections survives measurement.

What does not work is the tidy path. The official action writes `.npmrc`, and
`bunfig.toml` overrides it, so adopting the proxy for bun means putting the
proxy host into `bunfig.toml`. That reverses the change made earlier the same
day, whose whole point was that the project, not the machine, decides the
registry, and it makes every developer's `just ci` depend on proxy uptime. The
502 that started this question is exactly that failure.

## Not established

- Why the previous lockfile carried 39 explicit proxy URLs. A fresh resolution
  through the proxy records none, so the mechanism that produced them is not
  the one assumed.
- Whether the proxy's advisory data matches the public registry's in general.
  It matched for these 107 packages; that is not a guarantee for others.
- Whether the proxy blocks anything this dependency tree would actually hit.
  No malicious-package test was run against it.
- Whether `setup-takumi-guard-npm` has a bun-aware mode. Only its `.npmrc`
  behaviour was read.

## Recommendation

**Conditional: not now, and the condition is not about the proxy.**

Leave `bunfig.toml` on the public registry. The screened benefit lands on a
test-only fixture that is never published or deployed, and it is bought by
giving back the machine-independence just gained and by adding proxy uptime to
every local run of the gate. `just frontend-audit` already fails the build on a
high-severity advisory on every pull request.

Revisit when either of these changes:

1. `setup-takumi-guard-npm`, or bun itself, gains a way to set the registry that
   does not fight `bunfig.toml`. Then CI can be screened without changing what a
   developer resolves from.
2. This package stops being a fixture, or a second bun package appears that
   ships.

Separately, and independent of the above: Dependabot can be pointed at the proxy
on its own, through `registries` with `type: npm-registry` and
`replaces-base: true`, without touching `bunfig.toml` or local development.
That is the piece worth doing first if install-time screening is wanted, and it
is blocked today only because the bun updater cannot read bun 1.4's
`lockfileVersion 2`.
