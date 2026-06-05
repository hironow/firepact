"""The extractor must reproduce the frozen schema-layer golden and stamp the
x-firestore-* vocabulary correctly."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from firepact import build_realtime_bundle

import examples.chat.models  # noqa: F401  (import fires @firestore_realtime)

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_GOLDEN = REPO_ROOT / "fixtures" / "message.bundle.json"


def _bundle() -> dict[str, Any]:
    return build_realtime_bundle()


def _message_props() -> dict[str, Any]:
    props: dict[str, Any] = _bundle()["$defs"]["Message"]["properties"]
    return props


@pytest.mark.skipif(
    bool(os.environ.get("FIREPACT_PYDANTIC_MATRIX")),
    reason="schema-layer golden is frozen against the locked pydantic; the matrix "
    "checks semantics + the emit-layer golden (which ignores titles/ordering)",
)
def test_bundle_matches_schema_layer_golden() -> None:
    # given
    expected = json.loads(BUNDLE_GOLDEN.read_text(encoding="utf-8"))

    # when
    actual = _bundle()

    # then
    assert actual == expected


def test_wire_keys_are_camel_case() -> None:
    # given / when
    props = _message_props()

    # then
    assert "authorProfile" in props
    assert "createdAt" in props
    assert "author_profile" not in props
    assert "created_at" not in props


def test_reference_field_is_stamped() -> None:
    # given / when
    author = _message_props()["author"]

    # then
    assert author["x-firestore-type"] == "reference"
    assert author["x-firestore-ref-target"] == "Profile"


def test_server_timestamp_is_stamped() -> None:
    # given / when
    created = _message_props()["createdAt"]

    # then
    assert created["x-firestore-type"] == "timestamp"
    assert created["x-firestore-server-timestamp"] is True


def test_backfilled_field_is_presence_guaranteed() -> None:
    # given / when
    body = _message_props()["body"]

    # then
    assert body["x-firestore-presence-guaranteed"] is True


def test_integer_field_is_not_stamped() -> None:
    # given / when
    count = _bundle()["$defs"]["Reaction"]["properties"]["count"]

    # then
    assert "x-firestore-type" not in count
    assert count["type"] == "integer"


def test_root_carries_realtime_metadata() -> None:
    # given / when
    message = _bundle()["$defs"]["Message"]

    # then
    assert message["x-firestore-collection"] == "rooms/{roomId}/messages"
    assert message["x-firestore-doc-id-field"] == "id"
    assert "x-firestore-collection" not in _bundle()["$defs"]["Profile"]


def test_all_object_defs_use_camel_case_wire_keys() -> None:
    # Trap #1 guard at depth: every property key in every object def must be
    # camelCase, so a nested model that forgot the camel alias generator is caught.
    defs = _bundle()["$defs"]
    snake = [
        f"{name}.{key}"
        for name, node in defs.items()
        for key in node.get("properties", {})
        if "_" in key
    ]
    assert snake == [], f"non-camelCase wire keys (alias drift): {snake}"


def test_nested_profile_required_is_pinned() -> None:
    # avatar_url is `str | None` with NO default -> required (write view), even
    # though it is nullable. Locks the easy-to-drift required-ness.
    profile = _bundle()["$defs"]["Profile"]
    assert set(profile["required"]) == {"avatarUrl", "displayName"}
