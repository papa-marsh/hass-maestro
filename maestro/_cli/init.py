"""Implementation of `hass-maestro init`: scaffolds a new maestro project from templates."""

import re
from importlib import resources
from pathlib import Path
from string import Template

# Templates use string.Template syntax ($project_name, $timezone).
# Literal dollar signs in template files must be escaped as `$$`.
SCAFFOLD_FILES: tuple[tuple[str, str], ...] = (
    ("app.py.tmpl", "app.py"),
    ("pyproject.toml.tmpl", "pyproject.toml"),
    ("env.tmpl", ".env"),
    ("env.tmpl", ".env.example"),
    ("gitignore.tmpl", ".gitignore"),
    ("README.md.tmpl", "README.md"),
    ("AGENTS.md.tmpl", "AGENTS.md"),
    ("Dockerfile.tmpl", "Dockerfile"),
    ("docker-compose.yml.tmpl", "docker-compose.yml"),
    ("redis.conf.tmpl", "redis.conf"),
    ("justfile.tmpl", "justfile"),
    ("scripts_example.py.tmpl", "scripts/example.py"),
    ("scripts_tests_test_example.py.tmpl", "scripts/tests/test_example.py"),
)

EMPTY_PACKAGE_INIT_FILES: tuple[str, ...] = (
    "scripts/__init__.py",
    "scripts/tests/__init__.py",
    "registry/__init__.py",
    "custom_domains/__init__.py",
)


def run_init(directory: Path, timezone: str, force: bool) -> int:
    """Generate a new maestro project in the given directory. Returns a process exit code."""
    directory = directory.resolve()
    substitutions = {
        "project_name": _derive_project_name(directory.name),
        "timezone": timezone,
    }

    destinations = [dest for _, dest in SCAFFOLD_FILES] + list(EMPTY_PACKAGE_INIT_FILES)
    conflicts = [dest for dest in destinations if (directory / dest).exists()]
    if conflicts and not force:
        print(f"Refusing to overwrite existing files in {directory}:")
        for conflict in conflicts:
            print(f"  {conflict}")
        print("Re-run with --force to overwrite them.")
        return 1

    templates = resources.files("maestro._cli") / "templates"
    for template_name, dest in SCAFFOLD_FILES:
        content = Template((templates / template_name).read_text()).substitute(substitutions)
        _write(directory / dest, content)
    for dest in EMPTY_PACKAGE_INIT_FILES:
        _write(directory / dest, "")

    print(f"Initialized maestro project in {directory}")
    print()
    print("Next steps:")
    print("  1. Fill in HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN in .env")
    print("  2. uv sync                        # install dependencies")
    print("  3. uv run pytest                  # run the example test")
    print("  4. docker compose up -d --build   # deploy (app + redis + postgres)")
    return 0


def _derive_project_name(directory_name: str) -> str:
    """Sanitize a directory name into a valid package/compose project name."""
    name = re.sub(r"[^a-z0-9]+", "-", directory_name.lower()).strip("-")
    return name or "maestro-project"


def _write(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
