#!/usr/bin/env python3
"""Relative-link checker for the repo's markdown files.

For every ``[text](target)`` link in the tracked markdown (excluding vendored and
build directories), verify that:

- relative file targets resolve to an existing file or directory, and
- ``#anchor`` (same file) and ``file.md#anchor`` anchors point at a real heading
  (GitHub-style slug).

External (``http``/``https``/``mailto``/``tel``) links and image targets are
skipped. Exits non-zero if any relative link is broken, so CI can gate on it.

Stdlib only -- run with ``python3 scripts/check_links.py`` (no project env needed).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "target",
    "dist",
    "output",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}
LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)]+)\)")  # [text](target), not ![img]()
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:")


def md_files() -> list[Path]:
    return sorted(
        p
        for p in ROOT.rglob("*.md")
        if not any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)
    )


def slug(heading: str) -> str:
    """GitHub-style heading anchor slug."""
    s = re.sub(r"[`*_~]", "", heading.strip().lower())
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def anchors_of(path: Path) -> set[str]:
    out: set[str] = set()
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = HEADING_RE.match(line)
        if not m:
            continue
        base = slug(m.group(1))
        n = counts.get(base, 0)
        out.add(base if n == 0 else f"{base}-{n}")
        counts[base] = n + 1
    return out


def broken_links(md: Path) -> list[str]:
    found: list[str] = []
    rel = md.relative_to(ROOT)
    for target in LINK_RE.findall(md.read_text(encoding="utf-8")):
        target = target.strip()
        if target.startswith(EXTERNAL_PREFIXES):
            continue
        file_part, _, anchor = target.partition("#")
        if file_part == "":
            if anchor and anchor.lower() not in anchors_of(md):
                found.append(f"{rel}: missing anchor -> #{anchor}")
            continue
        dest = (md.parent / file_part).resolve()
        if not dest.exists():
            found.append(f"{rel}: broken link -> {target}")
        elif anchor and dest.suffix == ".md" and anchor.lower() not in anchors_of(dest):
            found.append(f"{rel}: broken anchor -> {target}")
    return found


def main() -> int:
    files = md_files()
    broken = [b for md in files for b in broken_links(md)]
    if broken:
        sys.stdout.write("BROKEN LINKS:\n")
        for b in broken:
            sys.stdout.write(f"  - {b}\n")
        return 1
    sys.stdout.write(
        f"OK: all relative links in {len(files)} markdown files resolve.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
