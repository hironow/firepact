"""End-to-end: a doc written by the Python backend (google-cloud-firestore)
through the real Firestore emulator is consumed by a TypeScript frontend that
compiles against the firepact-generated types and reads it via onSnapshot.

No mocks: real emulator, real subprocesses, real client SDK. Skipped when the
emulator or bun is unavailable.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from firepact import build_realtime_bundle
from firepact.cli import emit_typescript

import examples.chat.models  # noqa: F401  (import fires @firestore_realtime)

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "tests" / "e2e" / "frontend"
EMULATOR_HOST = "127.0.0.1"
EMULATOR_PORT = 8080
PROJECT = "demo-firepact"
DOC_PATH = "rooms/r1/messages/m1"


def _emulator_up() -> bool:
    try:
        with socket.create_connection((EMULATOR_HOST, EMULATOR_PORT), timeout=2):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _emulator_up(),
        reason=f"Firestore emulator not reachable on {EMULATOR_HOST}:{EMULATOR_PORT}",
    ),
    pytest.mark.skipif(shutil.which("bun") is None, reason="bun not installed"),
]


@pytest.fixture(scope="module")
def frontend_deps() -> None:
    if not (FRONTEND / "node_modules").exists():
        subprocess.run(
            ["bun", "install"], cwd=FRONTEND, check=True, capture_output=True
        )


@pytest.fixture(scope="module")
def generated_ts(frontend_deps: None) -> Path:
    out = FRONTEND / "generated.ts"
    out.write_text(emit_typescript(build_realtime_bundle()), encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def written_doc() -> Iterator[None]:
    os.environ["FIRESTORE_EMULATOR_HOST"] = f"{EMULATOR_HOST}:{EMULATOR_PORT}"
    from google.cloud import firestore

    db = firestore.Client(project=PROJECT)
    from google.cloud.firestore_v1.vector import Vector

    # camelCase wire keys (trap #1); doc-id excluded; createdAt via server sentinel.
    payload: dict[str, Any] = {
        "embedding": Vector([0.1, 0.2, 0.3]),
        "attachment": {"kind": "image", "url": "https://x/i.png", "width": 64},
        "author": db.document("profiles/p1"),
        "authorProfile": {"displayName": "Ada", "avatarUrl": None},
        "body": "hello from e2e",
        "createdAt": firestore.SERVER_TIMESTAMP,
        "editedAt": datetime(2020, 1, 2, tzinfo=UTC),
        "kind": "text",
        "location": firestore.GeoPoint(35.6, 139.7),
        "metadata": {"client": "web"},
        "pinned": True,
        "priority": 3,
        "reactions": [{"emoji": "thumbsup", "count": 2}],
        "selection": [0, 10],
        "tags": ["greeting"],
        "thumbnail": b"\x01\x02\x03",
    }
    ref = db.collection("rooms").document("r1").collection("messages").document("m1")
    ref.set(payload)
    yield
    ref.delete()


def test_generated_types_compile(generated_ts: Path) -> None:
    # given the generated read/write views + converter
    # when type-checking the consumer against them
    result = subprocess.run(
        ["bunx", "tsc", "--noEmit"],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        check=False,
    )
    # then there are no type errors
    assert result.returncode == 0, f"tsc failed:\n{result.stdout}\n{result.stderr}"


def test_onsnapshot_reads_written_doc(generated_ts: Path, written_doc: None) -> None:
    # given a doc written through the emulator
    env = {
        **os.environ,
        "GCLOUD_PROJECT": PROJECT,
        "FIRESTORE_EMULATOR_HOST": f"{EMULATOR_HOST}:{EMULATOR_PORT}",
    }

    # when the frontend subscribes via onSnapshot through the generated converter
    result = subprocess.run(
        ["bun", "run", "reader.ts"],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )

    # then it reads the doc with the contract intact
    assert result.returncode == 0, f"reader failed:\n{result.stdout}\n{result.stderr}"
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["id"] == "m1"
    assert payload["body"] == "hello from e2e"
    assert payload["kind"] == "text"
    assert payload["createdAtIsTimestamp"] is True
    assert payload["authorIsRef"] is True
    assert payload["editedAtIsTimestamp"] is True
    assert payload["locationIsGeoPoint"] is True
    assert payload["embeddingIsVector"] is True
    assert payload["thumbnailIsBytes"] is True
    assert payload["attachmentKind"] == "image"
    assert payload["selection"] == [0, 10]
    assert payload["pinnedIsBool"] is True
    assert payload["priorityIsNumber"] is True
    assert payload["avatarUrlIsNull"] is True
