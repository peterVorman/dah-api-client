#!/usr/bin/env python3
"""Validate the DAH API Client skill package without external dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED_FILES = (
    "SKILL.md",
    "LICENSE",
    "agents/openai.yaml",
    "references/client-usage.md",
    "references/commands.json",
    "references/configuration.md",
    "references/endpoints.md",
    "references/golden-prompts.md",
    "references/intent-router.md",
    "references/output-templates.md",
    "references/quality-gates.md",
    "references/safety-decision-table.md",
    "references/workflows.md",
    "references/write-operation-protocol.md",
)
REQUIRED_SKILL_SECTIONS = ("Quality Gates", "Endpoint Extension Checklist")
COMMAND_FIELDS = {
    "name",
    "mode",
    "requiresEnv",
    "supportsDryRun",
    "requiresApproval",
    "references",
}
COMMAND_MODES = {"read", "read-sensitive", "write", "local-write"}
PRODUCTION_FILES = (
    "dah_api.py",
    "auth_session.py",
    "cli_parser.py",
    "debtor_data.py",
    "debtor_notifications.py",
    "debtor_reports.py",
    "main.py",
)
DEPRECATED_MARKERS = (
    "DAH_" + "MESSENGER_GROUP_ID",
    "DEFAULT_" + "BEARER_TOKEN",
    "DEFAULT_" + "MESSENGER_GROUP_ID",
    "--" + "token",
)
LOCAL_PATH_MARKER = "/" + "Users" + "/"
REFERENCE_RE = re.compile(r"references/([A-Za-z0-9_.-]+)")
CLI_COMMAND_RE = re.compile(r"subparsers\.add_parser\(\s*[\"']([^\"']+)")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(DAH_(?:BEARER|REFRESH)_TOKEN|DAH_(?:LOGIN|PASSWORD))\s*=\s*(?![\"']?<)"
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
    errors.extend(reference_link_errors(skill_dir))
    errors.extend(commands_manifest_errors(skill_dir))
    errors.extend(quality_gate_errors(skill_dir))
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
    if path.is_file() and path.suffix in {".md", ".py", ".yaml", ".yml", ".json"}:
        text = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(skill_dir)
        if path.suffix == ".py":
            errors.extend(python_syntax_errors(path, relative_path, text))
        if LOCAL_PATH_MARKER in text:
            errors.append(f"{relative_path} contains a machine-local path")
        errors.extend(
            f"{relative_path} contains deprecated marker: {marker}"
            for marker in DEPRECATED_MARKERS
            if marker in text
        )
        if SECRET_ASSIGNMENT_RE.search(text):
            errors.append(f"{relative_path} contains a credential assignment")
    return errors


def python_syntax_errors(path: Path, relative_path: Path, text: str) -> list[str]:
    try:
        compile(text, str(path), "exec")
    except SyntaxError as exc:
        return [f"{relative_path} has invalid Python syntax: {exc.msg}"]
    return []


def reference_link_errors(skill_dir: Path) -> list[str]:
    errors = []
    for path in text_files(skill_dir):
        text = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(skill_dir)
        errors.extend(
            f"{relative_path} references missing references/{name}"
            for name in sorted(set(REFERENCE_RE.findall(text)))
            if not (skill_dir / "references" / name).is_file()
        )
    return errors


def text_files(skill_dir: Path) -> list[Path]:
    return [
        path
        for path in skill_dir.rglob("*")
        if path.is_file() and path.suffix in {".md", ".yaml", ".yml"}
    ]


def commands_manifest_errors(skill_dir: Path) -> list[str]:
    path = skill_dir / "references" / "commands.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"references/commands.json is invalid: {exc}"]

    commands = data.get("commands") if isinstance(data, dict) else None
    if not isinstance(commands, list) or not commands:
        return ["references/commands.json must contain a non-empty commands array"]
    errors = command_record_errors(skill_dir, commands)
    errors.extend(cli_command_coverage_errors(skill_dir, command_names(commands)))
    return errors


def command_record_errors(skill_dir: Path, commands: list[object]) -> list[str]:
    errors = []
    seen = set()
    for index, command in enumerate(commands):
        errors.extend(one_command_errors(skill_dir, command, index, seen))
    return errors


def one_command_errors(
    skill_dir: Path,
    command: object,
    index: int,
    seen: set[str],
) -> list[str]:
    if not isinstance(command, dict):
        return [f"commands[{index}] must be an object"]
    name = command.get("name")
    errors = required_command_field_errors(command, index)
    if isinstance(name, str):
        if name in seen:
            errors.append(f"commands[{index}] duplicate command: {name}")
        seen.add(name)
    else:
        errors.append(f"commands[{index}].name must be a string")
    errors.extend(command_type_errors(command, index))
    errors.extend(command_reference_errors(skill_dir, command, index))
    return errors


def required_command_field_errors(command: dict, index: int) -> list[str]:
    return [
        f"commands[{index}] missing {field}"
        for field in sorted(COMMAND_FIELDS)
        if field not in command
    ]


def command_type_errors(command: dict, index: int) -> list[str]:
    checks = {
        "requiresEnv": isinstance(command.get("requiresEnv"), list),
        "supportsDryRun": isinstance(command.get("supportsDryRun"), bool),
        "requiresApproval": isinstance(command.get("requiresApproval"), bool),
        "references": isinstance(command.get("references"), list),
        "mode": command.get("mode") in COMMAND_MODES,
    }
    return [
        f"commands[{index}].{field} has invalid value"
        for field, valid in checks.items()
        if not valid
    ]


def command_reference_errors(skill_dir: Path, command: dict, index: int) -> list[str]:
    references = command.get("references", [])
    return [
        f"commands[{index}] references missing {reference}"
        for reference in references
        if not isinstance(reference, str)
        or not (skill_dir / "references" / reference).is_file()
    ]


def command_names(commands: list[object]) -> set[str]:
    return {
        command["name"]
        for command in commands
        if isinstance(command, dict) and isinstance(command.get("name"), str)
    }


def cli_command_coverage_errors(skill_dir: Path, manifest_names: set[str]) -> list[str]:
    repo_root = repo_root_for(skill_dir)
    if not repo_root or not (repo_root / "cli_parser.py").is_file():
        return []
    cli_names = set(CLI_COMMAND_RE.findall((repo_root / "cli_parser.py").read_text()))
    return [
        *[
            f"references/commands.json missing CLI command: {name}"
            for name in sorted(cli_names - manifest_names)
        ],
        *[
            f"references/commands.json contains unknown CLI command: {name}"
            for name in sorted(manifest_names - cli_names)
        ],
    ]


def quality_gate_errors(skill_dir: Path) -> list[str]:
    paths = [skill_dir / "SKILL.md", skill_dir / "references" / "quality-gates.md"]
    repo_root = repo_root_for(skill_dir)
    if repo_root and (repo_root / ".github" / "workflows" / "ci.yml").is_file():
        paths.append(repo_root / ".github" / "workflows" / "ci.yml")
    return [
        f"{display_path(path, skill_dir)} missing quality gate file: {filename}"
        for path in paths
        for filename in PRODUCTION_FILES
        if filename not in path.read_text(encoding="utf-8")
    ]


def repo_root_for(skill_dir: Path) -> Path | None:
    for path in (skill_dir, *skill_dir.parents):
        if (path / ".git").exists():
            return path
    return None


def display_path(path: Path, skill_dir: Path) -> str:
    try:
        return str(path.relative_to(skill_dir))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
