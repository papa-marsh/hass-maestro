"""
Tests for MaestroApp construction: framework initialization, singleton registration,
script loading, and double-construction protection.
"""

import sys
from collections.abc import Generator
from pathlib import Path

import pytest

import maestro.app as app_module
from maestro import MaestroApp, get_app
from maestro.config import MaestroConfig, get_config, register_config
from maestro.exceptions import MaestroAlreadyConstructedError, MaestroNotConstructedError


@pytest.fixture
def clean_app_state() -> Generator[None]:
    """Restore the app singleton and test config after construction tests"""
    yield
    app_module._app = None
    register_config(MaestroConfig(hass_url="", hass_token="", redis_host="", redis_port=0))
    for module_name in [m for m in sys.modules if m == "scripts" or m.startswith("scripts.")]:
        del sys.modules[module_name]


def test_constructor_initializes_framework(tmp_path: Path, clean_app_state: None) -> None:
    """Test that construction registers config, loads scripts, and exposes the app singleton"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "automation.py").write_text("LOADED = True\n")

    app = MaestroApp(
        hass_url="http://hass.local:8123/",
        hass_token="token",
        redis_host="localhost",
        redis_port=6379,
        scripts_dir=scripts_dir,
        registry_dir=tmp_path / "registry",
        background_services=False,
        configure_logging=False,
    )

    assert get_app() is app

    config = get_config()
    assert config.hass_url == "http://hass.local:8123"
    assert config.scripts_dir == scripts_dir

    assert "scripts.automation" in sys.modules
    assert app.scheduler is not None
    assert not app.scheduler.running


def test_double_construction_raises(tmp_path: Path, clean_app_state: None) -> None:
    """Test that constructing a second MaestroApp in one process raises"""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    constructor_kwargs = {
        "hass_url": "http://hass.local:8123",
        "hass_token": "token",
        "redis_host": "localhost",
        "redis_port": 6379,
        "scripts_dir": scripts_dir,
        "background_services": False,
        "configure_logging": False,
    }
    MaestroApp(**constructor_kwargs)  # type:ignore[arg-type]

    with pytest.raises(MaestroAlreadyConstructedError):
        MaestroApp(**constructor_kwargs)  # type:ignore[arg-type]


def test_get_app_before_construction_raises(clean_app_state: None) -> None:
    """Test that get_app() raises a clear error before construction"""
    with pytest.raises(MaestroNotConstructedError):
        get_app()
