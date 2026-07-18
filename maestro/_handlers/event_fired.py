from maestro.integrations._home_assistant.types import FiredEvent, WebSocketEvent
from maestro.triggers._event_fired import EventFiredTriggerManager
from maestro.utils._logging import log


def handle_event_fired(event: WebSocketEvent) -> None:
    log.debug("Processing fired event", event_type=event.event_type)

    fired_event = FiredEvent(
        time_fired=event.time_fired,
        type=event.event_type,
        data=event.data,
        user_id=event.data.get("user_id") or event.context.user_id,
    )

    EventFiredTriggerManager.fire_triggers(fired_event)
