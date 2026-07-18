"""
Tests for WebSocket event handlers.
Verifies raw events are parsed into typed payloads and dispatched to triggers.
"""

from typing import Any

from maestro._handlers.event_fired import handle_event_fired
from maestro._handlers.notif_action import handle_notif_action
from maestro.integrations._home_assistant.types import (
    EventContext,
    FiredEvent,
    NotifActionEvent,
    WebSocketEvent,
)
from maestro.testing._maestro_test import MaestroTest
from maestro.triggers._event_fired import event_fired_trigger
from maestro.triggers._notif_action import notif_action_trigger
from maestro.utils._dates import local_now

captured_notif_actions: list[NotifActionEvent] = []
captured_events: list[FiredEvent] = []


@notif_action_trigger("handler_test_action")
def capture_notif_action(notif_action: NotifActionEvent) -> None:
    captured_notif_actions.append(notif_action)


@event_fired_trigger("handler_test_event")
def capture_event(event: FiredEvent) -> None:
    captured_events.append(event)


def build_websocket_event(
    event_type: str,
    data: dict[str, Any],
    context_user_id: str | None = None,
) -> WebSocketEvent:
    return WebSocketEvent(
        event_type=event_type,
        data=data,
        time_fired=local_now(),
        origin="REMOTE",
        context=EventContext(id="test_context", parent_id=None, user_id=context_user_id),
    )


def test_notif_action_without_action_data(mt: MaestroTest) -> None:
    """Test that notif action events missing the action_data key don't crash the handler"""
    captured_notif_actions.clear()

    event = build_websocket_event(
        event_type="ios.notification_action_fired",
        data={
            "actionName": "handler_test_action",
            "sourceDeviceID": "device_1",
            "sourceDeviceName": "Device One",
        },
    )
    handle_notif_action(event)

    assert len(captured_notif_actions) == 1
    assert captured_notif_actions[0].action_data is None


def test_notif_action_with_action_data(mt: MaestroTest) -> None:
    """Test that action_data is passed through when present"""
    captured_notif_actions.clear()

    event = build_websocket_event(
        event_type="ios.notification_action_fired",
        data={
            "actionName": "handler_test_action",
            "sourceDeviceID": "device_1",
            "sourceDeviceName": "Device One",
            "action_data": {"key": "value"},
        },
    )
    handle_notif_action(event)

    assert len(captured_notif_actions) == 1
    assert captured_notif_actions[0].action_data == {"key": "value"}


def test_event_fired_user_id_from_context(mt: MaestroTest) -> None:
    """Test that fired events take user_id from the event context by default"""
    captured_events.clear()

    event = build_websocket_event(
        event_type="handler_test_event",
        data={},
        context_user_id="context_user",
    )
    handle_event_fired(event)

    assert len(captured_events) == 1
    assert captured_events[0].user_id == "context_user"


def test_event_fired_data_user_id_overrides_context(mt: MaestroTest) -> None:
    """Test that an explicit user_id in event data takes precedence over the context user"""
    captured_events.clear()

    event = build_websocket_event(
        event_type="handler_test_event",
        data={"user_id": "explicit_user"},
        context_user_id="context_user",
    )
    handle_event_fired(event)

    assert len(captured_events) == 1
    assert captured_events[0].user_id == "explicit_user"
