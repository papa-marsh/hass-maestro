from maestro.domains._entity import Entity
from maestro.integrations._home_assistant.domain import Domain


class InputText(Entity):
    domain = Domain.INPUT_TEXT

    def set(self, value: str) -> None:
        self.perform_action("set_value", value=value)
