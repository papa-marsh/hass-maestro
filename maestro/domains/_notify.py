from maestro.domains._entity import Entity
from maestro.integrations._home_assistant.domain import Domain


class Notify(Entity):
    domain = Domain.NOTIFY
    allow_set_state = False
