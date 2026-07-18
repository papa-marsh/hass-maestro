"""Entry point for the `hass-maestro` command-line interface."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from maestro._cli.init import run_init

DEFAULT_TIMEZONE = "America/New_York"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hass-maestro",
        description="Command-line tools for the Maestro Home Assistant automation framework",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Scaffold a new maestro project",
        description="Generate a ready-to-run maestro project, including an app entrypoint, "
        "example automation scripts, and a Docker deployment stack.",
    )
    init_parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Target directory for the new project (default: current directory)",
    )
    init_parser.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help=f"IANA timezone for the generated config (default: {DEFAULT_TIMEZONE})",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files in the target directory",
    )

    args = parser.parse_args(argv)

    match args.command:
        case "init":
            return run_init(Path(args.directory), timezone=args.timezone, force=args.force)
        case _:
            parser.error(f"Unknown command: {args.command}")
