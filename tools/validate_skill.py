#!/usr/bin/env python3
"""Validate Load Tester Pro metadata and mirrored agent skill bundles."""
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = (".claude", ".claudecode", ".codex", ".manus", ".opencode", ".cline", ".ai-agent")
BUNDLE_FILES = (
    "SKILL.md",
    "scripts/k6/user-flow.js",
    "scripts/locust/locustfile.py",
    "scripts/locust/checkout_auth_flow.py",
    "scripts/run-k6.sh",
    "scripts/run-locust.sh",
    "scripts/summarize_results.py",
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"{path.relative_to(ROOT)} must start with YAML frontmatter")
    chunks = text.split("---", 2)
    if len(chunks) != 3 or chunks[0] != "":
        fail(f"{path.relative_to(ROOT)} has malformed YAML frontmatter delimiters")
    try:
        metadata = yaml.safe_load(chunks[1])
    except yaml.YAMLError as exc:
        fail(f"Invalid frontmatter in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(metadata, dict):
        fail(f"Frontmatter in {path.relative_to(ROOT)} must be a mapping")
    return metadata, chunks[2]


def main() -> None:
    canonical = ROOT / "SKILL.md"
    metadata, body = read_frontmatter(canonical)
    if metadata.get("name") != "load-tester-pro":
        fail("SKILL.md name must be load-tester-pro")
    if not isinstance(metadata.get("description"), str) or len(metadata["description"].strip()) < 30:
        fail("SKILL.md needs a descriptive, non-empty description")
    if len(canonical.read_text(encoding="utf-8").splitlines()) > 500:
        fail("SKILL.md must stay under 500 lines")
    if "[TODO" in canonical.read_text(encoding="utf-8"):
        fail("SKILL.md still contains a TODO placeholder")
    for relative in BUNDLE_FILES[1:]:
        if not (ROOT / relative).is_file():
            fail(f"Missing bundled resource: {relative}")
    for adapter in ADAPTERS:
        for relative in BUNDLE_FILES:
            source = ROOT / relative
            copy = ROOT / adapter / "skills" / "load-tester-pro" / relative
            if not copy.is_file():
                fail(f"Missing adapter file: {copy.relative_to(ROOT)}")
            if source.read_bytes() != copy.read_bytes():
                fail(f"Adapter copy differs from canonical {relative}: {copy.relative_to(ROOT)}")
    workflow = ROOT / ".github/workflows/validate-skill.yml"
    if not workflow.is_file():
        fail("Missing .github/workflows/validate-skill.yml")
    print("Skill metadata, resource files, and all seven agent bundles are valid and synchronized.")


if __name__ == "__main__":
    main()
