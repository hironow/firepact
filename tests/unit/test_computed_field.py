"""End-to-end guard for Pydantic @computed_field: it renders as readOnly in the
serialization-mode JSON Schema and must be present on read but excluded from the
write view (it is derived on the backend, not provided by the writer).

Uses models_json_schema directly so the global realtime registry (and the
message golden) is not affected.
"""

from __future__ import annotations

from typing import Any

from firepact import FirestoreJsonSchema
from firepact.cli import emit_typescript
from pydantic import BaseModel, computed_field
from pydantic.json_schema import models_json_schema


class Derived(BaseModel):
    x: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def doubled(self) -> int:
        return self.x * 2


def _bundle() -> dict[str, Any]:
    _keymap, bundle = models_json_schema(
        [(Derived, "serialization")],
        by_alias=True,
        ref_template="#/$defs/{model}",
        schema_generator=FirestoreJsonSchema,
    )
    return bundle


def test_pydantic_marks_computed_field_read_only() -> None:
    # given / when
    doubled = _bundle()["$defs"]["Derived"]["properties"]["doubled"]

    # then: this pins current Pydantic behavior (the premise of the emit rule)
    assert doubled.get("readOnly") is True


def test_computed_field_present_on_read_excluded_on_write() -> None:
    # given / when
    ts = emit_typescript(_bundle())
    read = ts.split("export interface Derived {")[1].split("}")[0]
    write = ts.split("export interface DerivedWrite {")[1].split("}")[0]

    # then
    assert "doubled" in read
    assert "doubled" not in write
    assert "x:" in write
