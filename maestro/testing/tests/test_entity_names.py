"""
Tests for entity, device, and area name resolution.
Verifies name lookups, caching, cache invalidation on registry updates, and response parsing.
"""

from http import HTTPMethod, HTTPStatus

import pytest

from maestro._handlers.event_fired import handle_event_fired
from maestro.domains import BinarySensor
from maestro.exceptions import EntityDoesNotExistError
from maestro.integrations._home_assistant.client import HomeAssistantClient
from maestro.integrations._home_assistant.types import EntityNames, FiredEvent
from maestro.testing._maestro_test import MaestroTest
from maestro.testing.tests.test_handlers import build_websocket_event
from maestro.triggers._event_fired import event_fired_trigger

west_stall = BinarySensor("binary_sensor.west_stall")

captured_registry_events: list[FiredEvent] = []


@event_fired_trigger("entity_registry_updated")
def capture_registry_event(event: FiredEvent) -> None:
    captured_registry_events.append(event)


def test_default_names_in_test_mode(mt: MaestroTest) -> None:
    """Test that unset names default to the title-cased entity ID with no device or area"""
    assert west_stall.entity_name == "West Stall"
    assert west_stall.device_name is None
    assert west_stall.area_name is None


def test_set_names_replaces_cached_names(mt: MaestroTest) -> None:
    """Test that set_names takes effect even after names were already cached"""
    assert west_stall.entity_name == "West Stall"

    mt.set_names(west_stall, "Stall", device_name="Stall Sensor", area_name="Garage")

    assert west_stall.entity_name == "Stall"
    assert west_stall.device_name == "Stall Sensor"
    assert west_stall.area_name == "Garage"


def test_registry_update_clears_cached_names(mt: MaestroTest) -> None:
    """Test that a registry update event invalidates cached names and still fires triggers"""
    captured_registry_events.clear()
    assert west_stall.entity_name == "West Stall"

    renamed = EntityNames(entity_name="Renamed", device_name=None, area_name=None)
    mt.hass_client.set_entity_names(west_stall.id, renamed)
    assert west_stall.entity_name == "West Stall"

    handle_event_fired(build_websocket_event("entity_registry_updated", data={}))

    assert west_stall.entity_name == "Renamed"
    assert len(captured_registry_events) == 1


def test_client_parses_template_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the client maps the rendered template into EntityNames"""
    response = {"entity_name": "West Stall", "device_name": "West Stall Sensor", "area_name": None}

    def fake_request(self: HomeAssistantClient, method: HTTPMethod, path: str, body: dict) -> tuple:
        return response, HTTPStatus.OK

    monkeypatch.setattr(HomeAssistantClient, "execute_request", fake_request)

    names = HomeAssistantClient().get_entity_names("binary_sensor.west_stall")

    assert names == EntityNames("West Stall", "West Stall Sensor", None)


def test_client_raises_for_missing_entity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a null entity name from Home Assistant means the entity doesn't exist"""
    response = {"entity_name": None, "device_name": None, "area_name": None}

    def fake_request(self: HomeAssistantClient, method: HTTPMethod, path: str, body: dict) -> tuple:
        return response, HTTPStatus.OK

    monkeypatch.setattr(HomeAssistantClient, "execute_request", fake_request)

    with pytest.raises(EntityDoesNotExistError):
        HomeAssistantClient().get_entity_names("binary_sensor.missing")
