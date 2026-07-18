from maestro.domains._entity import Entity
from maestro.integrations._home_assistant.domain import Domain


class Cover(Entity):
    domain = Domain.COVER
    allow_set_state = False

    def open_cover(self) -> None:
        self.perform_action("open_cover")

    def close_cover(self) -> None:
        self.perform_action("close_cover")

    def stop_cover(self) -> None:
        self.perform_action("stop_cover")

    def toggle(self) -> None:
        self.perform_action("toggle")
