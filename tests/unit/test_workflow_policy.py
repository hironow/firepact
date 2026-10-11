"""Keep pull-request jobs dormant while a pull request is a draft."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pull_request_workflow_resumes_when_ready() -> None:
    workflow = (ROOT / ".github/workflows/ci.yaml").read_text(encoding="utf-8")
    trigger = workflow.split("permissions:", maxsplit=1)[0]
    assert "ready_for_review" in trigger


def test_every_pull_request_job_skips_drafts() -> None:
    workflow = (ROOT / ".github/workflows/ci.yaml").read_text(encoding="utf-8")
    jobs = re.findall(
        r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)",
        workflow.split("jobs:\n", maxsplit=1)[1],
        re.MULTILINE | re.DOTALL,
    )
    assert jobs
    missing = [
        name
        for name, body in jobs
        if "github.event.pull_request.draft == false" not in body
    ]
    assert missing == []
