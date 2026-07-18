from maestro.domains._entity import Entity
from maestro.integrations._home_assistant.domain import Domain


class Lock(Entity):
    domain = Domain.LOCK
    allow_set_state = False

    def lock(self) -> None:
        self.perform_action("lock")

    def unlock(self) -> None:
        self.perform_action("unlock")
