"""
Tests for registry module generation: file creation, parent class preservation,
and the split between built-in and custom domain imports.
"""

from collections.abc import Generator
from pathlib import Path

import pytest

from maestro.config import MaestroConfig, register_config
from maestro.integrations.home_assistant.types import EntityData, EntityId
from maestro.registry.registry_manager import RegistryManager
from maestro.testing.maestro_test import MaestroTest
from maestro.utils.exceptions import CustomDomainsNotConfiguredError, MalformedRegistryModule


@pytest.fixture
def registry_dir(tmp_path: Path) -> Generator[Path]:
    """Point the registry at a temp directory, restoring the default test config after"""
    register_config(
        MaestroConfig(
            hass_url="",
            hass_token="",
            redis_host="",
            redis_port=0,
            registry_dir=tmp_path / "registry",
            custom_domains_dir=tmp_path / "custom_domains",
        )
    )
    yield tmp_path / "registry"
    register_config(MaestroConfig(hass_url="", hass_token="", redis_host="", redis_port=0))


def test_write_new_module_generates_entity_class(mt: MaestroTest, registry_dir: Path) -> None:
    """Test that a new registry module contains the entity class, instance, and imports"""
    entity_data = EntityData(
        entity_id=EntityId("light.desk_lamp"),
        state="on",
        attributes={"brightness": 128, "friendly_name": "Desk Lamp"},
    )

    RegistryManager.write_new_module(entity_data)

    content = (registry_dir / "light.py").read_text()
    assert "from maestro.domains import Light" in content
    assert "class LightDeskLamp(Light):" in content
    assert "brightness = EntityAttribute(int)" in content
    assert 'desk_lamp = LightDeskLamp("light.desk_lamp")' in content
    assert "friendly_name" not in content


def test_update_preserves_custom_parent_class(mt: MaestroTest, registry_dir: Path) -> None:
    """Test that updating an entity keeps its user-assigned custom domain parent"""
    entity_data = EntityData(
        entity_id=EntityId("climate.thermostat"),
        state="heat",
        attributes={"current_temperature": 68.5},
    )
    RegistryManager.write_new_module(entity_data)

    # Simulate the user promoting the generated class to a custom domain parent
    module_filepath = registry_dir / "climate.py"
    module_filepath.write_text(module_filepath.read_text().replace("(Climate)", "(Thermostat)"))

    RegistryManager.update_existing_module(entity_data)

    content = module_filepath.read_text()
    assert "class ClimateThermostat(Thermostat):" in content
    assert "from custom_domains import Thermostat" in content
    assert "from maestro.domains import" not in content


def test_mixed_parents_generate_dual_imports(mt: MaestroTest, registry_dir: Path) -> None:
    """Test that built-in and custom parents import from their respective packages"""
    upstairs = EntityData(entity_id=EntityId("climate.upstairs"), state="heat", attributes={})
    downstairs = EntityData(entity_id=EntityId("climate.downstairs"), state="heat", attributes={})
    RegistryManager.write_new_module(upstairs)

    # Simulate the user promoting one entity to a custom domain parent
    module_filepath = registry_dir / "climate.py"
    module_filepath.write_text(
        module_filepath.read_text().replace(
            "class ClimateUpstairs(Climate):", "class ClimateUpstairs(Thermostat):"
        )
    )

    RegistryManager.update_existing_module(downstairs)

    content = module_filepath.read_text()
    assert "from maestro.domains import Climate" in content
    assert "from custom_domains import Thermostat" in content
    assert "class ClimateUpstairs(Thermostat):" in content
    assert "class ClimateDownstairs(Climate):" in content


def test_reformatted_module_raises_instead_of_dropping_entries(
    mt: MaestroTest, registry_dir: Path
) -> None:
    """Test that rewriting a module with formatter-wrapped statements fails loudly"""
    long_name = "sensor.a_very_long_entity_name_that_would_exceed_the_line_length_limit"
    entity_data = EntityData(entity_id=EntityId(long_name), state="1", attributes={})
    RegistryManager.write_new_module(entity_data)

    # Simulate a code formatter wrapping the instantiation across multiple lines
    module_filepath = registry_dir / "sensor.py"
    content = module_filepath.read_text()
    class_name = "SensorAVeryLongEntityNameThatWouldExceedTheLineLengthLimit"
    content = content.replace(
        f'a_very_long_entity_name_that_would_exceed_the_line_length_limit = {class_name}("{long_name}")',
        f'a_very_long_entity_name_that_would_exceed_the_line_length_limit = {class_name}(\n    "{long_name}"\n)',
    )
    module_filepath.write_text(content)

    with pytest.raises(MalformedRegistryModule):
        RegistryManager.update_existing_module(entity_data)


def test_custom_parent_without_custom_domains_dir_raises(mt: MaestroTest, tmp_path: Path) -> None:
    """Test that custom parents raise a clear error when custom_domains_dir is unset"""
    register_config(
        MaestroConfig(
            hass_url="",
            hass_token="",
            redis_host="",
            redis_port=0,
            registry_dir=tmp_path / "registry",
        )
    )
    entity_data = EntityData(entity_id=EntityId("climate.thermostat"), state="heat", attributes={})
    RegistryManager.write_new_module(entity_data)
    module_filepath = tmp_path / "registry" / "climate.py"
    module_filepath.write_text(module_filepath.read_text().replace("(Climate)", "(Thermostat)"))

    try:
        with pytest.raises(CustomDomainsNotConfiguredError):
            RegistryManager.update_existing_module(entity_data)
    finally:
        register_config(MaestroConfig(hass_url="", hass_token="", redis_host="", redis_port=0))
