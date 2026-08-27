#!/usr/bin/env python3
"""Validate the DAH API Client skill package without external dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_FILES = (
    "SKILL.md",
    "LICENSE",
    "agents/openai.yaml",
    "references/client-usage.md",
)
REQUIRED_SKILL_SECTIONS = ("Quality Gates", "Endpoint Extension Checklist")
LOCAL_PATH_MARKER = "/" + "Users" + "/"
SECRET_ASSIGNMENT_RE = re.compile(
    r"(DAH_(?:BEARER|REFRESH)_TOKEN|DAH_PASSWORD)\s*=\s*(?![\"']?<)"
)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    skill_dir = Path(args[0]) if args else Path(".codex/skills/dah-api-client")
    errors = validate_skill(skill_dir)
    if errors:
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Skill package OK: {skill_dir}")
    return 0


def validate_skill(skill_dir: Path) -> list[str]:
    errors = missing_files(skill_dir)
    if errors:
        return errors

    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    metadata = frontmatter_metadata(skill_text)
    errors.extend(
        f"SKILL.md frontmatter missing {field}" for field in ("name", "description")
        if not metadata.get(field)
    )
    errors.extend(
        f"SKILL.md missing section: {section}"
        for section in REQUIRED_SKILL_SECTIONS
        if section not in skill_text
    )
    errors.extend(local_data_errors(skill_dir))
    return errors


def missing_files(skill_dir: Path) -> list[str]:
    return [
        f"missing required file: {relative_path}"
        for relative_path in REQUIRED_FILES
        if not (skill_dir / relative_path).is_file()
    ]


def frontmatter_metadata(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}
    metadata: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata


def local_data_errors(skill_dir: Path) -> list[str]:
    return [
        error
        for path in skill_dir.rglob("*")
        for error in local_data_file_errors(path, skill_dir)
    ]


def local_data_file_errors(path: Path, skill_dir: Path) -> list[str]:
    errors = []
    if path.is_file() and path.suffix in {".md", ".py", ".yaml", ".yml"}:
        text = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(skill_dir)
        if path.suffix == ".py":
            errors.extend(python_syntax_errors(path, relative_path, text))
        if LOCAL_PATH_MARKER in text:
            errors.append(f"{relative_path} contains a machine-local path")
        if SECRET_ASSIGNMENT_RE.search(text):
            errors.append(f"{relative_path} contains a credential assignment")
    return errors


def python_syntax_errors(path: Path, relative_path: Path, text: str) -> list[str]:
    try:
        compile(text, str(path), "exec")
    except SyntaxError as exc:
        return [f"{relative_path} has invalid Python syntax: {exc.msg}"]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
