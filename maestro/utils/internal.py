"""
Internal utility logic & helpers.
Not intended to be used by script modules
"""

import importlib
import logging
import sys
from collections.abc import Mapping, MutableMapping
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from maestro.config import get_config
from maestro.exceptions import MissingScriptsDirectoryError
from maestro.utils.logging import log


def test_mode_active() -> bool:
    return "pytest" in sys.modules


def add_timezone_timestamp(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> Mapping[str, Any]:
    """Add timestamp in configured timezone."""
    event_dict["timestamp"] = datetime.now(get_config().timezone).isoformat()
    return event_dict


def configure_logging() -> None:
    """Configure structlog with colored output for all environments."""
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            add_timezone_timestamp,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(min_level=logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to use structlog's output
    # This captures logs from libraries like APScheduler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
        )
    )

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


def import_custom_domains() -> None:
    """
    Import the user's custom domains package (if configured) so its Entity subclasses
    are defined before registry modules and scripts that reference them are loaded.
    """
    custom_domains_dir = get_config().custom_domains_dir
    if custom_domains_dir is None:
        return

    importlib.invalidate_caches()
    importlib.import_module(custom_domains_dir.name)
    log.info("Imported custom domains package", package=custom_domains_dir.name)


def load_script_modules(scripts_dir: Path) -> None:
    """
    Auto-discover and import all Python modules in the scripts directory.
    This ensures that trigger decorators (eg. @state_change_trigger) and DB models get registered.

    Modules are imported as a package named after the directory (eg. `scripts.family.ellie`),
    which requires the project root to already be on `sys.path`.
    """
    scripts_dir = scripts_dir.resolve()
    if not scripts_dir.exists():
        raise MissingScriptsDirectoryError(f"Scripts directory not found: {scripts_dir}")

    # The path finder caches directory listings; project dirs may be newer than the cache
    importlib.invalidate_caches()

    package_name = scripts_dir.name
    loaded_count = 0
    error_count = 0

    for python_file in sorted(scripts_dir.rglob("*.py")):
        if python_file.name.startswith("_") or python_file.name.startswith("test"):
            continue

        relative_path = python_file.relative_to(scripts_dir)
        module_name = f"{package_name}.{'.'.join(relative_path.with_suffix('').parts)}"

        try:
            log.info("Loading scripts module", module=module_name)
            importlib.import_module(module_name)
            loaded_count += 1
        except Exception as e:
            log.exception("Failed to load scripts module", module=module_name, error=str(e))
            error_count += 1

    log.info("Script loading completed", loaded=loaded_count, errors=error_count)
