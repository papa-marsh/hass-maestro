from maestro.integrations._home_assistant.types import FiredEvent, WebSocketEvent
from maestro.integrations._state_manager import StateManager
from maestro.triggers._event_fired import EventFiredTriggerManager
from maestro.utils._logging import log

NAME_REGISTRY_EVENT_TYPES = {
    "entity_registry_updated",
    "device_registry_updated",
    "area_registry_updated",
}


def handle_event_fired(event: WebSocketEvent) -> None:
    log.debug("Processing fired event", event_type=event.event_type)

    if event.event_type in NAME_REGISTRY_EVENT_TYPES:
        keys_deleted = StateManager().delete_all_cached_entity_names()
        log.debug(
            "Cleared cached entity names after registry update",
            event_type=event.event_type,
            keys_deleted=keys_deleted,
        )

    fired_event = FiredEvent(
        time_fired=event.time_fired,
        type=event.event_type,
        data=event.data,
        user_id=event.data.get("user_id") or event.context.user_id,
    )

    EventFiredTriggerManager.fire_triggers(fired_event)
