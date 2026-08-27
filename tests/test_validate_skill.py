import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".codex" / "skills" / "dah-api-client"
VALIDATOR_PATH = SKILL_DIR / "scripts" / "validate_skill.py"


def validator_module():
    spec = importlib.util.spec_from_file_location("validate_skill", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_skill_package_validates():
    assert validator_module().validate_skill(SKILL_DIR) == []


def test_validate_skill_reports_manifest_errors(tmp_path):
    skill_dir = tmp_path / "dah-api-client"
    shutil.copytree(SKILL_DIR, skill_dir)
    (skill_dir / "references" / "commands.json").write_text(
        '{"commands":[{"name":"access","mode":"bad","references":["missing.md"]}]}',
        encoding="utf-8",
    )

    errors = validator_module().validate_skill(skill_dir)

    assert any("supportsDryRun" in error for error in errors)
    assert any("invalid value" in error for error in errors)
    assert any("references missing missing.md" in error for error in errors)
