from maestro.domains._entity import HOME, Entity
from maestro.integrations._home_assistant.domain import Domain


class DeviceTracker(Entity):
    domain = Domain.DEVICE_TRACKER
    allow_set_state = False

    @property
    def is_home(self) -> bool:
        return self.state == HOME
