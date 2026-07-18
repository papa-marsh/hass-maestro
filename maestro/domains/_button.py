from maestro.domains._entity import Entity
from maestro.integrations._home_assistant.domain import Domain


class Button(Entity):
    domain = Domain.BUTTON
    allow_set_state = False

    def press(self) -> None:
        self.perform_action("press")
