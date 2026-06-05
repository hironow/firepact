"""Coverage for Python paths the happy-path tests miss: module-path validation,
binary resolution, the public APIs, multi-root / id_field=None, and the
FirestoreBackfilled since_version branch."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import pytest
from firepact import FirestoreBackfilled, FirestoreJsonSchema, firestore_realtime
from firepact import cli as cli_mod
from firepact.cli import bundle_for_module, find_binary, generate_typescript_defs
from firepact.firestore_select import _REGISTRY, build_realtime_bundle, registered_roots
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from pydantic.json_schema import models_json_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
TS_GOLDEN = REPO_ROOT / "fixtures" / "message.generated.ts"


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def test_bundle_for_module_rejects_invalid_path() -> None:
    with pytest.raises(ValueError, match="invalid module path"):
        bundle_for_module("not a module; rm -rf /")


def test_find_binary_honors_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREPACT_BIN", "/custom/firepact")
    assert find_binary() == "/custom/firepact"


def test_generate_typescript_defs_writes_output(tmp_path: Path) -> None:
    out = tmp_path / "types.ts"
    ts = generate_typescript_defs("examples.chat.models", output=str(out))
    assert ts == TS_GOLDEN.read_text(encoding="utf-8")
    assert out.read_text(encoding="utf-8") == ts


def test_registered_roots_includes_the_example_root() -> None:
    import examples.chat.models as chat

    assert chat.Message in registered_roots()


def test_main_with_output_matches_golden(tmp_path: Path) -> None:
    out = tmp_path / "types.ts"
    code = cli_mod.main(["--module", "examples.chat.models", "--output", str(out)])
    assert code == 0
    assert out.read_text(encoding="utf-8") == TS_GOLDEN.read_text(encoding="utf-8")


def test_backfilled_without_since_version_omits_presence_since() -> None:
    class Doc(BaseModel):
        f: Annotated[str, FirestoreBackfilled()]
        g: Annotated[str, FirestoreBackfilled(since_version="v2")]

    _keymap, bundle = models_json_schema(
        [(Doc, "serialization")],
        by_alias=True,
        schema_generator=FirestoreJsonSchema,
    )
    props = bundle["$defs"]["Doc"]["properties"]
    assert props["f"]["x-firestore-presence-guaranteed"] is True
    assert "x-firestore-presence-since" not in props["f"]
    assert props["g"]["x-firestore-presence-since"] == "v2"


def test_multiple_roots_and_id_field_none() -> None:
    # Isolate the process-global registry so other tests (and the golden) are unaffected.
    saved = dict(_REGISTRY)
    _REGISTRY.clear()
    try:

        @firestore_realtime(collection="a/{x}/items", id_field="id")
        class _A(_Camel):
            id: str
            v: int

        @firestore_realtime(collection="b", id_field=None)
        class _B(_Camel):
            name: str

        defs: dict[str, Any] = build_realtime_bundle()["$defs"]
        assert defs["_A"]["x-firestore-collection"] == "a/{x}/items"
        assert defs["_A"]["x-firestore-doc-id-field"] == "id"
        assert defs["_B"]["x-firestore-collection"] == "b"
        assert "x-firestore-doc-id-field" not in defs["_B"]  # id_field=None
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(saved)
