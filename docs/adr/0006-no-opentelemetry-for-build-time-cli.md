# 0006. No OpenTelemetry for a build-time codegen CLI

**Date:** 2026-06-05
**Status:** Accepted

## Context

The org-wide observability standard requires every service to emit OpenTelemetry
traces. firepact is not a service: it is a build-time codegen / contract-gate CLI
invoked in developer shells and CI. It has no inbound RPC/HTTP, no message bus,
no LLM calls -- none of the standard's minimum-coverage span sites apply.

DESIGN S9 pins the core as a single static binary with zero Node dependency and
no implicit coupling. Adding an OTel SDK + OTLP exporter would contradict that
(heavier binary, runtime endpoint config) for traces nobody collects on a
per-invocation CLI.

## Decision

Exclude OpenTelemetry from firepact. This is an explicit, requester-confirmed
deviation from the global observability standard, justified by firepact being a
build-time tool rather than a service.

## Consequences

### Positive
- The binary stays single-file and dependency-light (DESIGN S9).

### Negative
- No distributed traces for firepact invocations; debugging relies on exit codes,
  stderr, and the deterministic golden/compat output.

### Neutral
- If firepact ever grows a long-running server mode, this ADR should be
  superseded and OTel added there.
