"""Tests for the `hass-maestro init` project scaffolding command"""

import ast
from pathlib import Path

from maestro._cli.init import EMPTY_PACKAGE_INIT_FILES, SCAFFOLD_FILES
from maestro._cli.main import main


def _all_destinations() -> list[str]:
    return [dest for _, dest in SCAFFOLD_FILES] + list(EMPTY_PACKAGE_INIT_FILES)


def test_init_scaffolds_complete_project(tmp_path: Path) -> None:
    """Init generates every scaffold file with all template variables substituted"""
    project_dir = tmp_path / "my-project"

    exit_code = main(["init", str(project_dir), "--timezone", "Europe/London"])

    assert exit_code == 0
    for dest in _all_destinations():
        assert (project_dir / dest).is_file(), f"Missing scaffold file: {dest}"

    for dest in _all_destinations():
        content = (project_dir / dest).read_text()
        assert "$project_name" not in content, f"Unsubstituted placeholder in {dest}"
        assert "$timezone" not in content, f"Unsubstituted placeholder in {dest}"

    assert "Europe/London" in (project_dir / ".env").read_text()
    assert 'name = "my-project"' in (project_dir / "pyproject.toml").read_text()
    assert "name: my-project" in (project_dir / "docker-compose.yml").read_text()


def test_init_generates_valid_python(tmp_path: Path) -> None:
    """Every generated Python module parses"""
    project_dir = tmp_path / "my-project"

    main(["init", str(project_dir)])

    for path in project_dir.rglob("*.py"):
        ast.parse(path.read_text(), filename=str(path))


def test_init_env_files_match(tmp_path: Path) -> None:
    """Generated .env and .env.example have identical contents"""
    project_dir = tmp_path / "my-project"

    main(["init", str(project_dir)])

    assert (project_dir / ".env").read_text() == (project_dir / ".env.example").read_text()


def test_init_refuses_existing_files(tmp_path: Path) -> None:
    """Init fails without overwriting when target files already exist"""
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("original content")

    exit_code = main(["init", str(project_dir)])

    assert exit_code == 1
    assert (project_dir / "app.py").read_text() == "original content"
    assert not (project_dir / "pyproject.toml").exists()


def test_init_force_overwrites(tmp_path: Path) -> None:
    """Init with --force overwrites existing files"""
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("original content")

    exit_code = main(["init", str(project_dir), "--force"])

    assert exit_code == 0
    assert (project_dir / "app.py").read_text() != "original content"


def test_init_sanitizes_project_name(tmp_path: Path) -> None:
    """Directory names are sanitized into valid package and compose project names"""
    project_dir = tmp_path / "My Automations!"

    exit_code = main(["init", str(project_dir)])

    assert exit_code == 0
    assert 'name = "my-automations"' in (project_dir / "pyproject.toml").read_text()
