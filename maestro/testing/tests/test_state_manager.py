"""
Tests for StateManager entity initialization and cache retrieval.
Verifies initialize_hass_entity creation, restore_cached behavior, and fetch_cached_entity reads.
"""

from maestro.integrations._home_assistant.types import AttributeId, EntityId
from maestro.testing._maestro_test import MaestroTest
from maestro.utils._dates import local_now


def test_initialize_hass_entity_creates_new_entity(mt: MaestroTest) -> None:
    """Test that initialize_hass_entity creates a new entity when it doesn't exist"""
    entity_id = EntityId("sensor.test_sensor")

    entity_data, created = mt.state_manager.initialize_hass_entity(
        entity_id=entity_id,
        state="25",
        attributes={"unit": "°C", "battery": 100},
    )

    assert created is True
    assert entity_data.entity_id == entity_id
    assert entity_data.state == "25"
    assert entity_data.attributes["unit"] == "°C"
    assert entity_data.attributes["battery"] == 100


def test_initialize_hass_entity_returns_existing_entity(mt: MaestroTest) -> None:
    """Test that initialize_hass_entity returns existing entity without creating duplicate"""
    entity_id = EntityId("sensor.test_sensor")

    mt.set_state(entity_id, "25", {"unit": "°C", "battery": 100})

    entity_data, created = mt.state_manager.initialize_hass_entity(
        entity_id=entity_id,
        state="30",
        attributes={"unit": "°F", "battery": 50},
    )

    assert created is False
    assert entity_data.state == "25"
    assert entity_data.attributes["unit"] == "°C"
    assert entity_data.attributes["battery"] == 100


def test_initialize_hass_entity_with_restore_cached_no_cache(mt: MaestroTest) -> None:
    """Test restore_cached=True when no cached entity exists"""
    entity_id = EntityId("sensor.test_sensor")

    entity_data, created = mt.state_manager.initialize_hass_entity(
        entity_id=entity_id,
        state="25",
        attributes={"unit": "°C"},
        restore_cached=True,
    )

    assert created is True
    assert entity_data.state == "25"
    assert entity_data.attributes["unit"] == "°C"


def test_initialize_hass_entity_with_restore_cached_from_cache(mt: MaestroTest) -> None:
    """Test restore_cached=True restores entity from cache when available"""
    entity_id = EntityId("sensor.test_sensor")

    mt.state_manager.set_cached_state(entity_id, "42")
    temp_attr = AttributeId(f"{entity_id}.temperature")
    battery_attr = AttributeId(f"{entity_id}.battery")
    mt.state_manager.set_cached_state(temp_attr, 42)
    mt.state_manager.set_cached_state(battery_attr, 85)

    entity_data, created = mt.state_manager.initialize_hass_entity(
        entity_id=entity_id,
        state="0",
        attributes={"temperature": 0, "battery": 0, "new_attr": "test"},
        restore_cached=True,
    )

    assert created is True
    assert entity_data.state == "42"
    assert entity_data.attributes["temperature"] == 42
    assert entity_data.attributes["battery"] == 85
    assert entity_data.attributes["new_attr"] == "test"


def test_initialize_hass_entity_restore_cached_false_ignores_cache(mt: MaestroTest) -> None:
    """Test restore_cached=False ignores cached values"""
    entity_id = EntityId("sensor.test_sensor")

    mt.state_manager.set_cached_state(entity_id, "42")
    temp_attr = AttributeId(f"{entity_id}.temperature")
    mt.state_manager.set_cached_state(temp_attr, 42)

    entity_data, created = mt.state_manager.initialize_hass_entity(
        entity_id=entity_id,
        state="25",
        attributes={"temperature": 25},
        restore_cached=False,
    )

    assert created is True
    assert entity_data.state == "25"
    assert entity_data.attributes["temperature"] == 25


def test_fetch_cached_entity_returns_none_when_no_state(mt: MaestroTest) -> None:
    """Test fetch_cached_entity returns None when entity state is not cached"""
    entity_id = EntityId("sensor.nonexistent")

    result = mt.state_manager.fetch_cached_entity(entity_id)

    assert result is None


def test_fetch_cached_entity_returns_entity_data(mt: MaestroTest) -> None:
    """Test fetch_cached_entity returns EntityData with state and attributes"""
    entity_id = EntityId("sensor.test_sensor")
    now = local_now()

    mt.set_state(
        entity_id,
        "25",
        {
            "unit": "°C",
            "battery": 85,
            "last_updated": now,
            "sensors": ["indoor", "outdoor"],
        },
    )

    cached_entity = mt.state_manager.fetch_cached_entity(entity_id)

    assert cached_entity is not None
    assert cached_entity.entity_id == entity_id
    assert cached_entity.state == "25"
    assert cached_entity.attributes["unit"] == "°C"
    assert cached_entity.attributes["battery"] == 85
    assert cached_entity.attributes["last_updated"] == now
    assert cached_entity.attributes["sensors"] == ["indoor", "outdoor"]


def test_fetch_cached_entity_with_only_state_no_attributes(mt: MaestroTest) -> None:
    """Test fetch_cached_entity works when entity has state but no attributes"""
    entity_id = EntityId("sensor.simple_sensor")

    mt.state_manager.set_cached_state(entity_id, "on")

    cached_entity = mt.state_manager.fetch_cached_entity(entity_id)

    assert cached_entity is not None
    assert cached_entity.entity_id == entity_id
    assert cached_entity.state == "on"
    assert cached_entity.attributes == {}


def test_fetch_cached_entity_handles_multiple_attributes(mt: MaestroTest) -> None:
    """Test fetch_cached_entity correctly retrieves all attributes"""
    entity_id = EntityId("climate.thermostat")

    mt.set_state(
        entity_id,
        "heat",
        {
            "temperature": 22,
            "current_temperature": 20,
            "humidity": 45,
            "hvac_modes": ["heat", "cool", "off"],
            "target_temp_high": 25,
            "target_temp_low": 18,
        },
    )

    cached_entity = mt.state_manager.fetch_cached_entity(entity_id)

    assert cached_entity is not None
    assert cached_entity.state == "heat"
    assert cached_entity.attributes["temperature"] == 22
    assert cached_entity.attributes["current_temperature"] == 20
    assert cached_entity.attributes["humidity"] == 45
    assert cached_entity.attributes["hvac_modes"] == ["heat", "cool", "off"]
    assert cached_entity.attributes["target_temp_high"] == 25
    assert cached_entity.attributes["target_temp_low"] == 18


def test_initialize_hass_entity_existing_entity_ignores_restore_cached(mt: MaestroTest) -> None:
    """Test that restore_cached is ignored when entity already exists in HASS"""
    entity_id = EntityId("sensor.existing")

    mt.set_state(entity_id, "original", {"value": 100})

    mt.state_manager.set_cached_state(entity_id, "cached")
    value_attr = AttributeId(f"{entity_id}.value")
    mt.state_manager.set_cached_state(value_attr, 200)

    entity_data, created = mt.state_manager.initialize_hass_entity(
        entity_id=entity_id,
        state="new",
        attributes={"value": 300},
        restore_cached=True,
    )

    assert created is False
    assert entity_data.state == "original"
    assert entity_data.attributes["value"] == 100


def test_initialize_hass_entity_restore_merges_attributes(mt: MaestroTest) -> None:
    """Test that restore_cached merges cached attributes with new attributes"""
    entity_id = EntityId("sensor.merged")

    mt.state_manager.set_cached_state(entity_id, "cached_state")
    attr1 = AttributeId(f"{entity_id}.cached_attr")
    attr2 = AttributeId(f"{entity_id}.shared_attr")
    mt.state_manager.set_cached_state(attr1, "cached_value")
    mt.state_manager.set_cached_state(attr2, "cached_shared")

    entity_data, created = mt.state_manager.initialize_hass_entity(
        entity_id=entity_id,
        state="new_state",
        attributes={
            "new_attr": "new_value",
            "shared_attr": "new_shared",
        },
        restore_cached=True,
    )

    assert created is True
    assert entity_data.state == "cached_state"
    assert entity_data.attributes["cached_attr"] == "cached_value"
    assert entity_data.attributes["new_attr"] == "new_value"
    assert entity_data.attributes["shared_attr"] == "cached_shared"
