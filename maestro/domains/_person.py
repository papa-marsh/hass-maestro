from maestro._config import get_config
from maestro.domains._entity import HOME, Entity
from maestro.integrations._home_assistant.domain import Domain
from maestro.utils._internal import test_mode_active
from maestro.utils._push import Notif


class Person(Entity):
    domain = Domain.PERSON
    allow_set_state = False

    @property
    def notify_action_name(self) -> str:
        if test_mode_active():
            return f"test_mock_notify_{self.id.entity}"

        return get_config().notify_action_mappings.get(self.id, "")

    @property
    def is_home(self) -> bool:
        return self.state == HOME

    def notify(self, message: str) -> None:
        notif = Notif(message=message)
        notif.send(self)
