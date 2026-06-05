"""The compat example: its current model must match the latest frozen schema and
stay compatible with every committed past version (the FULL_TRANSITIVE gate)."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

from firepact.cli import bundle_for_module, check_compat
from firepact.firestore_select import _REGISTRY

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "examples" / "compat" / "schemas"
_MODELS = "examples.compat.models"


def _current_bundle_json() -> str:
    # Isolate the registry so the example's roots don't leak into other tests.
    saved = dict(_REGISTRY)
    _REGISTRY.clear()
    try:
        importlib.reload(importlib.import_module(_MODELS))
        bundle = bundle_for_module(_MODELS)
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(saved)
    return json.dumps(bundle, sort_keys=True)


def test_current_model_matches_latest_schema() -> None:
    # the newest committed schema must equal the current model's bundle
    latest = json.loads((SCHEMAS / "account.v1.json").read_text(encoding="utf-8"))
    current = json.loads(_current_bundle_json())
    assert current == latest


def test_current_is_compatible_with_all_history() -> None:
    current = _current_bundle_json()
    history = sorted(SCHEMAS.glob("*.json"))
    names = {p.name for p in history}
    assert {"account.v0.json", "account.v1.json"} <= names
    for past in history:
        findings = check_compat(past.read_text(encoding="utf-8"), current)
        breaking = [f for f in findings if f["verdict"] == "BREAKING"]
        assert not breaking, f"{past.name} -> current has breaking changes: {breaking}"
