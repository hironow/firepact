"""Trap #1 guard: the wire keys the extractor freezes into the bundle MUST equal
the keys the backend actually writes via ``model_dump(by_alias=True)``.

A mismatch (e.g. codegen by_alias=True but backend by_alias=False) type-checks
fine yet makes every field ``undefined`` at runtime, so it is pinned here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from firepact import build_realtime_bundle

from examples.chat.models import (
    ImageAttachment,
    Message,
    MessageKind,
    Profile,
    Reaction,
)


def _sample_message() -> Message:
    return Message(
        id="m1",
        attachment=ImageAttachment(kind="image", url="https://x/i.png", width=64),
        author="rooms/r1/profiles/p1",
        author_profile=Profile(display_name="Ada", avatar_url=None),
        body="hello",
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
        edited_at=datetime(2020, 1, 2, tzinfo=UTC),
        kind=MessageKind.TEXT,
        location=(35.6, 139.7),
        metadata={"client": "web"},
        reactions=[Reaction(emoji="thumbsup", count=2)],
        tags=["greeting"],
        thumbnail=b"\x01\x02\x03",
    )


def test_dumped_keys_equal_bundle_property_keys() -> None:
    # given
    bundle_keys = set(build_realtime_bundle()["$defs"]["Message"]["properties"])

    # when
    dumped_keys = set(_sample_message().model_dump(by_alias=True))

    # then
    assert dumped_keys == bundle_keys


def test_nested_model_dumps_camel_case() -> None:
    # given / when
    dumped = _sample_message().model_dump(by_alias=True)

    # then
    assert set(dumped["authorProfile"]) == {"displayName", "avatarUrl"}


def test_guard_is_meaningful_snake_case_would_not_match() -> None:
    # given
    bundle_keys = set(build_realtime_bundle()["$defs"]["Message"]["properties"])

    # when: the WRONG convention (by_alias=False) produces snake_case keys
    wrong_keys = set(_sample_message().model_dump(by_alias=False))

    # then: which would NOT match the contract -- proving the guard above bites
    assert wrong_keys != bundle_keys
    assert "author_profile" in wrong_keys
