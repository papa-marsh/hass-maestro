from maestro.integrations._home_assistant.types import WebSocketEvent
from maestro.triggers._hass import HassEvent, HassTriggerManager
from maestro.utils._logging import log


def handle_hass_startup(_event: WebSocketEvent) -> None:
    log.info("Processing Home Assistant startup event")
    HassTriggerManager.fire_triggers(HassEvent.STARTUP)
