"""
Tests for fired event tracking and assertions in the testing framework.
Verifies that events fired via fire_event() are recorded and can be asserted against.
"""

import pytest

from maestro.testing._maestro_test import MaestroTest


def test_mock_client_fired_event_tracking(mt: MaestroTest) -> None:
    """Test that mock client tracks fired events with their data"""
    mt.hass_client.fire_event("custom_event", key="value")

    mt.assert_event_fired("custom_event")
    mt.assert_event_fired("custom_event", key="value")

    events = mt.get_fired_events("custom_event")
    assert len(events) == 1
    assert events[0].data == {"key": "value"}


def test_fired_event_filtering(mt: MaestroTest) -> None:
    """Test filtering fired events by event type"""
    mt.hass_client.fire_event("event_one")
    mt.hass_client.fire_event("event_two", source="test")
    mt.hass_client.fire_event("event_one")

    assert len(mt.get_fired_events()) == 3
    assert len(mt.get_fired_events("event_one")) == 2
    assert len(mt.get_fired_events("event_two")) == 1


def test_assert_event_not_fired(mt: MaestroTest) -> None:
    """Test that assert_event_not_fired passes and fails appropriately"""
    mt.hass_client.fire_event("other_event")

    mt.assert_event_not_fired("custom_event")

    with pytest.raises(AssertionError):
        mt.assert_event_not_fired("other_event")


def test_assert_event_fired_data_mismatch(mt: MaestroTest) -> None:
    """Test that assert_event_fired fails when event data doesn't match"""
    mt.hass_client.fire_event("custom_event", key="value")

    with pytest.raises(AssertionError):
        mt.assert_event_fired("custom_event", key="wrong_value")


def test_clear_fired_events(mt: MaestroTest) -> None:
    """Test that clear_fired_events removes all recorded events"""
    mt.hass_client.fire_event("custom_event")
    mt.clear_fired_events()

    mt.assert_event_not_fired("custom_event")
